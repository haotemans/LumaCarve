//! Persistent capacity accounting for leases, not actual CUDA memory moves.
//! A Python adapter must synchronize CUDA before releasing a live lease.
use crate::graph::SchedulerError;
use std::collections::BTreeMap;

#[derive(Copy, Clone, Debug, Default, PartialEq, Eq)]
pub struct Reservation {
    pub gpu_bytes: u64,
    pub cpu_bytes: u64,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct ResourceBudget {
    pub gpu_bytes: u64,
    pub cpu_bytes: u64,
}

#[derive(Debug)]
pub struct MemoryArbiter {
    budget: ResourceBudget,
    used: Reservation,
    leases: BTreeMap<String, Reservation>,
}

impl MemoryArbiter {
    pub fn new(budget: ResourceBudget) -> Self {
        Self { budget, used: Reservation::default(), leases: BTreeMap::new() }
    }
    pub fn reserve(&mut self, id: &str, request: Reservation) -> Result<(), SchedulerError> {
        if id.trim().is_empty() || self.leases.contains_key(id) {
            return Err(SchedulerError("Empty or duplicate memory lease ID".into()));
        }
        let next_gpu = self.used.gpu_bytes.checked_add(request.gpu_bytes)
            .ok_or_else(|| SchedulerError("GPU reservation overflow".into()))?;
        let next_cpu = self.used.cpu_bytes.checked_add(request.cpu_bytes)
            .ok_or_else(|| SchedulerError("RAM reservation overflow".into()))?;
        if next_gpu > self.budget.gpu_bytes || next_cpu > self.budget.cpu_bytes {
            return Err(SchedulerError("Resource budget exceeded".into()));
        }
        self.leases.insert(id.into(), request);
        self.used = Reservation { gpu_bytes: next_gpu, cpu_bytes: next_cpu };
        Ok(())
    }
    pub fn release(&mut self, id: &str) -> Result<Reservation, SchedulerError> {
        let reserved = self.leases.remove(id)
            .ok_or_else(|| SchedulerError(format!("Missing memory lease: {id}")))?;
        self.used.gpu_bytes -= reserved.gpu_bytes;
        self.used.cpu_bytes -= reserved.cpu_bytes;
        Ok(reserved)
    }
    pub fn used(&self) -> Reservation { self.used }
    pub fn budget(&self) -> ResourceBudget { self.budget }
}
