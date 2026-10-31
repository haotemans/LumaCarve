//! CPU-only contract tests. Rust metadata policies do not load any model.
use lumacarve_scheduler::{
    compile, fingerprints, CancelOutcome, FingerprintNode, JobPriority, JobScheduler,
    JobState, MemoryArbiter, NodeSpec, Reservation, ResourceBudget,
};
use serde_json::json;
use std::collections::BTreeMap;

fn node(id: &str, depends_on: &[&str], component: &str) -> NodeSpec {
    NodeSpec {
        node_id: id.into(), operation: id.into(),
        depends_on: depends_on.iter().map(|x| (*x).into()).collect(),
        components: if component.is_empty() {vec![]} else {vec![component.into()]},
    }
}
#[test]
fn graph_topological_order_last_uses() {
    let input = vec![
        node("vae", &["dit"], "vae"),
        node("te", &[], "te"),
        node("dit", &["te"], "dit"),
    ];
    let plan = compile(&input).unwrap();
    assert_eq!(plan.order, vec!["te", "dit", "vae"]);
    assert_eq!(plan.last_output_use["te"], 1);
    assert_eq!(plan.last_output_use["dit"], 2);
    assert_eq!(plan.last_component_use["te"], 0);
    assert_eq!(plan.output_nodes, vec!["vae"]);
}
#[test]
fn graph_detects_errors() {
    assert!(compile(&[node("a", &["b"], "")]).is_err());
    assert!(compile(&[node("a", &["b"], ""), node("b", &["a"], "")]).is_err());
    assert!(compile(&[node("a", &[], ""), node("a", &[], "")]).is_err());
    assert!(compile(&[node("a", &[], " "),]).is_err());
}
fn cache_node(id: &str, inputs: &[&str], params: serde_json::Value) -> FingerprintNode {
    FingerprintNode {
        node_id: id.into(), operation: id.into(),
        depends_on: inputs.iter().map(|x| (*x).into()).collect(),
        params: params.as_object().unwrap().iter().map(|(k,v)| (k.clone(),v.clone())).collect(),
        model_revision: Some("sha256:weights-v1".into()), asset_hashes: vec![],
        volatile_nonce: None, volatile: false,
    }
}
#[test]
fn only_dependent_fingerprints_change() {
    let before = vec![
        cache_node("te", &[], json!({"prompt":"cat"})),
        cache_node("dit", &["te"], json!({"seed":100})),
        cache_node("other", &[], json!({"name":"unchanged"})),
    ];
    let mut after = before.clone();
    after[1].params.insert("seed".into(), json!(101));
    let a = fingerprints(&before).unwrap();
    let b = fingerprints(&after).unwrap();
    assert_eq!(a["te"], b["te"]);
    assert_ne!(a["dit"], b["dit"]);
    assert_eq!(a["other"], b["other"]);
    // Repeating identical inputs is stable.
    assert_eq!(a, fingerprints(&before).unwrap());
}
#[test]
fn volatile_requires_explicit_nonce() {
    let mut n = cache_node("random", &[], json!({}));
    n.volatile = true;
    assert!(fingerprints(&[n.clone()]).is_err());
    n.volatile_nonce = Some("job-1".into());
    let a = fingerprints(&[n.clone()]).unwrap();
    n.volatile_nonce = Some("job-2".into());
    let b = fingerprints(&[n]).unwrap();
    assert_ne!(a, b);
}
#[test]
fn interactive_queue_is_bounded_and_fair() {
    let mut queue = JobScheduler::new(12).unwrap();
    queue.submit("background", JobPriority::Background).unwrap();
    for id in ["a", "b", "c", "d"] {
        queue.submit(id, JobPriority::Interactive).unwrap();
    }
    assert_eq!(queue.start_next().as_deref(), Some("a"));
    assert!(queue.start_next().is_none()); // no concurrent GPU jobs
    assert_eq!(queue.finish("a", true).unwrap(), JobState::Completed);
    for id in ["b","c"] {
        assert_eq!(queue.start_next().as_deref(), Some(id));
        queue.finish(id, true).unwrap();
    }
    assert_eq!(queue.start_next().as_deref(), Some("background"));
    queue.finish("background", true).unwrap();
    assert_eq!(queue.start_next().as_deref(), Some("d"));
}
#[test]
fn cancellation_never_interrupts_running_kernel() {
    let mut queue = JobScheduler::new(2).unwrap();
    queue.submit("running", JobPriority::Interactive).unwrap();
    queue.submit("pending", JobPriority::Normal).unwrap();
    assert_eq!(queue.start_next().as_deref(), Some("running"));
    assert_eq!(queue.cancel("pending").unwrap(), CancelOutcome::CancelledBeforeStart);
    assert_eq!(queue.state("pending"), Some(JobState::Cancelled));
    assert_eq!(queue.cancel("running").unwrap(), CancelOutcome::RequestedRunning);
    assert!(queue.should_cancel("running"));
    assert_eq!(queue.finish("running", true).unwrap(), JobState::Cancelled);
    assert!(queue.running().is_none());
}
#[test]
fn memory_leases_enforce_budget_no_duplicate() {
    let mut arbiter = MemoryArbiter::new(ResourceBudget {gpu_bytes:8,cpu_bytes:16});
    arbiter.reserve("dit", Reservation {gpu_bytes:6,cpu_bytes:1}).unwrap();
    assert!(arbiter.reserve("dit", Reservation {gpu_bytes:1,cpu_bytes:1}).is_err());
    assert!(arbiter.reserve("vae", Reservation {gpu_bytes:4,cpu_bytes:1}).is_err());
    assert_eq!(arbiter.used().gpu_bytes, 6);
    arbiter.release("dit").unwrap();
    arbiter.reserve("vae", Reservation {gpu_bytes:4,cpu_bytes:1}).unwrap();
    assert_eq!(arbiter.used().gpu_bytes, 4);
}
