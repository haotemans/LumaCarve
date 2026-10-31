//! One-GPU resource queue: interactive jobs get priority without starving others.
//! SQLite in Python remains the durable source of truth during migration.
use crate::graph::SchedulerError;
use std::collections::BTreeMap;

#[derive(Copy, Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
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
        let has_non_interactive = self.queue.iter().any(|item| item.priority != JobPriority::Interactive);
        let force_other = self.consecutive_interactive >= 3 && has_non_interactive;
        let position = self.queue.iter().enumerate()
            .filter(|(_, item)| !force_other || item.priority != JobPriority::Interactive)
            .min_by_key(|(_, item)| (item.priority, item.sequence))
            .map(|(index, _)| index)?;
        let item = self.queue.remove(position);
        if item.priority == JobPriority::Interactive {
            self.consecutive_interactive += 1;
        } else {
            self.consecutive_interactive = 0;
        }
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
