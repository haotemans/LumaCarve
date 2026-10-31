//! PyO3 boundary: metadata JSON and small scalar control messages only.
//! No Python callback is run with an active Rust mutex or resource lease.
use crate::cache::{fingerprints, FingerprintNode};
use crate::graph::{compile, NodeSpec, SchedulerError};
use crate::incremental::{plan_incremental, CachedOutput};
use std::collections::BTreeMap;
use crate::queue::{select_job, JobPriority, JobScheduler, JobState, PendingJob};
use crate::resources::{MemoryArbiter, Reservation, ResourceBudget};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

fn python_error(error: SchedulerError) -> PyErr {
    PyValueError::new_err(error.0)
}

#[pyfunction]
fn compile_graph_json(nodes_json: &str) -> PyResult<String> {
    let nodes: Vec<NodeSpec> =
        serde_json::from_str(nodes_json).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let plan = compile(&nodes).map_err(python_error)?;
    serde_json::to_string(&plan).map_err(|err| PyValueError::new_err(err.to_string()))
}

#[pyfunction]
fn fingerprints_json(nodes_json: &str) -> PyResult<String> {
    let nodes: Vec<FingerprintNode> =
        serde_json::from_str(nodes_json).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let signatures = fingerprints(&nodes).map_err(python_error)?;
    serde_json::to_string(&signatures).map_err(|err| PyValueError::new_err(err.to_string()))
}


/// Choose from a SQLite pending snapshot; does NOT enqueue or claim anything.
#[pyfunction]
fn choose_queued_job(pending_json: &str, interactive_streak: u32)
    -> PyResult<Option<(String, u32)>>
{
    let pending: Vec<PendingJob> = serde_json::from_str(pending_json)
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    let decision = select_job(&pending, interactive_streak).map_err(python_error)?;
    Ok(decision.map(|choice| (choice.id, choice.next_interactive_streak)))
}


#[pyfunction]
fn plan_incremental_json(
    nodes_json: &str,
    cached_json: &str,
    output_ids_json: &str,
) -> PyResult<String> {
    let nodes: Vec<FingerprintNode> = serde_json::from_str(nodes_json)
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    let cached: BTreeMap<String, CachedOutput> = serde_json::from_str(cached_json)
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    let outputs: Vec<String> = serde_json::from_str(output_ids_json)
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    let plan = plan_incremental(&nodes, &cached, &outputs).map_err(python_error)?;
    serde_json::to_string(&plan).map_err(|err| PyValueError::new_err(err.to_string()))
}

fn py_priority(value: &str) -> PyResult<JobPriority> {
    match value {
        "interactive" => Ok(JobPriority::Interactive),
        "normal" => Ok(JobPriority::Normal),
        "background" => Ok(JobPriority::Background),
        _ => Err(PyValueError::new_err("priority must be interactive, normal or background")),
    }
}

fn py_state(state: JobState) -> &'static str {
    match state {
        JobState::Queued => "queued",
        JobState::Running => "running",
        JobState::Completed => "completed",
        JobState::Failed => "failed",
        JobState::Cancelled => "cancelled",
    }
}

#[pyclass]
struct RustJobScheduler {
    inner: JobScheduler,
}

#[pymethods]
impl RustJobScheduler {
    #[new]
    fn new(maximum_active: usize) -> PyResult<Self> {
        let inner = JobScheduler::new(maximum_active).map_err(python_error)?;
        Ok(Self { inner })
    }

    fn submit(&mut self, id: &str, priority: &str) -> PyResult<()> {
        self.inner.submit(id, py_priority(priority)?).map_err(python_error)
    }

    fn start_next(&mut self) -> Option<String> {
        self.inner.start_next()
    }

    fn cancel(&mut self, id: &str) -> PyResult<&'static str> {
        use crate::queue::CancelOutcome;
        let outcome = self.inner.cancel(id).map_err(python_error)?;
        Ok(match outcome {
            CancelOutcome::CancelledBeforeStart => "cancelled",
            CancelOutcome::RequestedRunning => "requested",
            CancelOutcome::AlreadyTerminal => "terminal",
        })
    }

    fn should_cancel(&self, id: &str) -> bool {
        self.inner.should_cancel(id)
    }

    fn finish(&mut self, id: &str, succeeded: bool) -> PyResult<&'static str> {
        let state = self.inner.finish(id, succeeded).map_err(python_error)?;
        Ok(py_state(state))
    }

    fn state(&self, id: &str) -> Option<&'static str> {
        self.inner.state(id).map(py_state)
    }

    fn running(&self) -> Option<String> {
        self.inner.running().map(str::to_string)
    }

    fn pending_count(&self) -> usize {
        self.inner.pending_count()
    }
}

#[pyclass]
struct RustMemoryArbiter {
    inner: MemoryArbiter,
}

#[pymethods]
impl RustMemoryArbiter {
    #[new]
    fn new(gpu_budget: u64, cpu_budget: u64) -> Self {
        Self {
            inner: MemoryArbiter::new(ResourceBudget {
                gpu_bytes: gpu_budget, cpu_bytes: cpu_budget,
            }),
        }
    }

    fn reserve(&mut self, id: &str, gpu_bytes: u64, cpu_bytes: u64) -> PyResult<()> {
        self.inner.reserve(id, Reservation { gpu_bytes, cpu_bytes }).map_err(python_error)
    }

    fn release(&mut self, id: &str) -> PyResult<(u64, u64)> {
        let released = self.inner.release(id).map_err(python_error)?;
        Ok((released.gpu_bytes, released.cpu_bytes))
    }

    fn used(&self) -> (u64, u64) {
        let reserved = self.inner.used();
        (reserved.gpu_bytes, reserved.cpu_bytes)
    }
}

/// A single Python extension installed into the project's existing .venv.
#[pymodule]
fn lumacarve_scheduler(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_graph_json, m)?)?;
    m.add_function(wrap_pyfunction!(fingerprints_json, m)?)?;
    m.add_function(wrap_pyfunction!(plan_incremental_json, m)?)?;
    m.add_function(wrap_pyfunction!(choose_queued_job, m)?)?;
    m.add_class::<RustJobScheduler>()?;
    m.add_class::<RustMemoryArbiter>()?;
    Ok(())
}
