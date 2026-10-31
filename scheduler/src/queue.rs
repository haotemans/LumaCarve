//! One-GPU resource queue: interactive jobs get priority without starving others.
//! SQLite in Python remains the durable source of truth during migration.
use crate::graph::SchedulerError;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::collections::BTreeMap;

#[derive(Copy, Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum JobPriority {
    Interactive = 0,
    Normal = 1,
    Background = 2,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum JobState {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum CancelOutcome {
    CancelledBeforeStart,
    RequestedRunning,
    AlreadyTerminal,
}


/// Snapshot of a SQLite queued job. Sequence is the durable SQLite rowid, not
/// an index in an ephemeral Rust queue, so ordering survives app restarts.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PendingJob {
    pub id: String,
    pub priority: JobPriority,
    pub sequence: u64,
}

/// A scheduling decision, not a state transition. SQLite must atomically
/// claim the returned ID before a Python adapter is allowed to execute it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JobChoice {
    pub id: String,
    pub priority: JobPriority,
    pub next_interactive_streak: u32,
}

/// Select exactly one task from a durable pending snapshot. There is NO
/// second in-memory execution queue. After three interactive jobs, serve the
/// OLDEST normal/background job to prevent starvation.
pub fn select_job(pending: &[PendingJob], interactive_streak: u32)
    -> Result<Option<JobChoice>, SchedulerError>
{
    let mut seen = HashSet::new();
    for job in pending {
        if job.id.trim().is_empty() || !seen.insert(job.id.as_str()) {
            return Err(SchedulerError("Empty or duplicate queued job ID".into()));
        }
    }
    let force_other = interactive_streak >= 3 &&
        pending.iter().any(|job| job.priority != JobPriority::Interactive);
    let next = if force_other {
        pending.iter()
            .filter(|job| job.priority != JobPriority::Interactive)
            .min_by_key(|job| (job.sequence, job.id.as_str()))
    } else {
        pending.iter()
            .min_by_key(|job| (job.priority, job.sequence, job.id.as_str()))
    };
    Ok(next.map(|job| JobChoice {
        id: job.id.clone(),
        priority: job.priority,
        next_interactive_streak: if job.priority == JobPriority::Interactive {
            interactive_streak.saturating_add(1).min(3)
        } else {
            0
        },
    }))
}

#[derive(Clone, Debug)]
struct Queued {
    id: String,
    priority: JobPriority,
    sequence: u64,
}

#[derive(Debug)]
pub struct JobScheduler {
    maximum_active: usize,
    queue: Vec<Queued>,
    states: BTreeMap<String, JobState>,
    running: Option<String>,
    cancel_requested: bool,
    next_sequence: u64,
    consecutive_interactive: usize,
}

impl JobScheduler {
    pub fn new(maximum_active: usize) -> Result<Self, SchedulerError> {
        if maximum_active == 0 || maximum_active > 1024 {
            return Err(SchedulerError("maximum_active must be 1..=1024".into()));
        }
        Ok(Self {
            maximum_active, queue: Vec::new(), states: BTreeMap::new(),
            running: None, cancel_requested: false, next_sequence: 0,
            consecutive_interactive: 0,
        })
    }
    pub fn submit(&mut self, id: &str, priority: JobPriority) -> Result<(), SchedulerError> {
        if id.trim().is_empty() || self.states.contains_key(id) {
            return Err(SchedulerError("Empty or duplicate job ID".into()));
        }
        if self.queue.len() + usize::from(self.running.is_some()) >= self.maximum_active {
            return Err(SchedulerError("Queue admission limit reached".into()));
        }
        let sequence = self.next_sequence;
        self.next_sequence = self.next_sequence.checked_add(1)
            .ok_or_else(|| SchedulerError("Queue sequence exhausted".into()))?;
        self.queue.push(Queued { id: id.into(), priority, sequence });
        self.states.insert(id.into(), JobState::Queued);
        Ok(())
    }
    pub fn start_next(&mut self) -> Option<String> {
        if self.running.is_some() || self.queue.is_empty() {
            return None;
        }
        // Reuse the same snapshot policy as the SQLite-backed Python bridge.
        let snapshot: Vec<PendingJob> = self.queue.iter().map(|job| PendingJob {
            id: job.id.clone(), priority: job.priority, sequence: job.sequence,
        }).collect();
        let picked = select_job(&snapshot, self.consecutive_interactive as u32)
            .expect("internal queued IDs are always valid")?;
        let position = self.queue.iter().position(|job| job.id == picked.id)?;
        let item = self.queue.remove(position);
        self.consecutive_interactive = picked.next_interactive_streak as usize;
        self.states.insert(item.id.clone(), JobState::Running);
        self.running = Some(item.id.clone());
        self.cancel_requested = false;
        Some(item.id)
    }
    pub fn cancel(&mut self, id: &str) -> Result<CancelOutcome, SchedulerError> {
        match self.states.get(id).copied() {
            None => Err(SchedulerError(format!("Unknown job {id}"))),
            Some(JobState::Queued) => {
                self.queue.retain(|queued| queued.id != id);
                self.states.insert(id.into(), JobState::Cancelled);
                Ok(CancelOutcome::CancelledBeforeStart)
            },
            Some(JobState::Running) => {
                self.cancel_requested = true;
                Ok(CancelOutcome::RequestedRunning)
            },
            _ => Ok(CancelOutcome::AlreadyTerminal),
        }
    }
    pub fn should_cancel(&self, id: &str) -> bool {
        self.running.as_deref() == Some(id) && self.cancel_requested
    }
    pub fn finish(&mut self, id: &str, succeeded: bool) -> Result<JobState, SchedulerError> {
        if self.running.as_deref() != Some(id) {
            return Err(SchedulerError("Job is not the currently running task".into()));
        }
        let next_state = if self.cancel_requested { JobState::Cancelled }
            else if succeeded { JobState::Completed } else { JobState::Failed };
        self.states.insert(id.into(), next_state);
        self.running = None;
        self.cancel_requested = false;
        Ok(next_state)
    }
    pub fn state(&self, id: &str) -> Option<JobState> {
        self.states.get(id).copied()
    }
    pub fn running(&self) -> Option<&str> {
        self.running.as_deref()
    }
    pub fn pending_count(&self) -> usize {
        self.queue.len()
    }
}
