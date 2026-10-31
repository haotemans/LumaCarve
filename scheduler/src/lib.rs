//! LumaCarve model-agnostic scheduling policy.
//! No CUDA, PyTorch, Python, GPU memory or model tensor is owned here.
pub mod cache;
pub mod graph;
pub mod incremental;
pub mod queue;
pub mod resources;

#[cfg(feature = "python")]
mod python;

pub use cache::{fingerprints, FingerprintNode};
pub use graph::{compile, ExecutionPlan, NodeSpec, SchedulerError};
pub use incremental::{plan_incremental, CachedOutput, IncrementalPlan, IncrementalStep, StepAction};
pub use queue::{select_job, CancelOutcome, JobChoice, JobPriority, JobScheduler, JobState, PendingJob};
pub use resources::{MemoryArbiter, Reservation, ResourceBudget};
