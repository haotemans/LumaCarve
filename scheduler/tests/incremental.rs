use lumacarve_scheduler::{
    fingerprints, plan_incremental, CachedOutput, FingerprintNode, StepAction,
};
use serde_json::json;
use std::collections::BTreeMap;

fn node(id: &str, deps: &[&str], params: serde_json::Value) -> FingerprintNode {
    FingerprintNode {
        node_id: id.into(),
        operation: id.into(),
        depends_on: deps.iter().map(|x| (*x).into()).collect(),
        params: params.as_object().unwrap().iter().map(|(k,v)| (k.clone(),v.clone())).collect(),
        model_revision: Some("sha256:model-v1".into()),
        asset_hashes: vec![],
        volatile_nonce: None,
        volatile: false,
    }
}
fn graph(seed: i32) -> Vec<FingerprintNode> {
    vec![
        node("encode", &[], json!({"prompt":"a star"})),
        node("sample", &["encode"], json!({"seed":seed})),
        node("decode", &["sample"], json!({})),
        node("unrelated", &[], json!({})),
    ]
}

#[test]
fn cache_hit_stops_upstream_and_skips_unrelated_branch() {
    let nodes = graph(1);
    let ids = fingerprints(&nodes).unwrap();
    let mut known = BTreeMap::new();
    known.insert("decode".to_string(), CachedOutput {
        fingerprint: ids["decode"].clone(), available: true,
    });
    let plan = plan_incremental(&nodes, &known, &["decode".into()]).unwrap();
    assert_eq!(plan.steps.len(), 1);
    assert_eq!(plan.steps[0].node_id, "decode");
    assert_eq!(plan.steps[0].action, StepAction::Reuse);
    assert_eq!(plan.executed, 0);
    assert_eq!(plan.reused, 1);
}

#[test]
fn changing_seed_preserves_text_embedding_but_recomputes_diffusion() {
    let before = graph(1);
    let after = graph(2);
    let signatures = fingerprints(&before).unwrap();
    let mut known = BTreeMap::new();
    known.insert("encode".into(), CachedOutput {
        fingerprint: signatures["encode"].clone(), available: true,
    });
    known.insert("decode".into(), CachedOutput {
        fingerprint: signatures["decode"].clone(), available: true,
    });
    let plan = plan_incremental(&after, &known, &["decode".into()]).unwrap();
    let decisions: Vec<_> = plan.steps.iter().map(|s| (&s.node_id,s.action)).collect();
    assert_eq!(decisions, vec![
        (&"encode".to_string(), StepAction::Reuse),
        (&"sample".to_string(), StepAction::Execute),
        (&"decode".to_string(), StepAction::Execute),
    ]);
    assert_eq!(plan.reused, 1);
    assert_eq!(plan.executed, 2);
}

#[test]
fn evicted_output_must_be_recomputed() {
    let nodes = graph(1);
    let signatures = fingerprints(&nodes).unwrap();
    let mut known = BTreeMap::new();
    known.insert("decode".into(), CachedOutput {
        fingerprint: signatures["decode"].clone(), available: false,
    });
    let plan = plan_incremental(&nodes, &known, &["decode".into()]).unwrap();
    assert_eq!(plan.executed, 3);
    assert_eq!(plan.reused, 0);
}

#[test]
fn volatile_nodes_always_execute_and_require_nonce() {
    let mut nodes = graph(1);
    nodes[1].volatile = true;
    assert!(plan_incremental(&nodes, &BTreeMap::new(), &["decode".into()]).is_err());
    nodes[1].volatile_nonce = Some("job-17".into());
    let hashes = fingerprints(&nodes).unwrap();
    let mut known = BTreeMap::new();
    known.insert("sample".into(), CachedOutput {
        fingerprint: hashes["sample"].clone(), available: true,
    });
    let plan = plan_incremental(&nodes, &known, &["decode".into()]).unwrap();
    assert_eq!(plan.steps.iter().find(|s| s.node_id == "sample").unwrap().action, StepAction::Execute);
}

#[test]
fn invalid_outputs_and_cyclic_graph_fail_closed() {
    let nodes = graph(1);
    assert!(plan_incremental(&nodes, &BTreeMap::new(), &["unknown".into()]).is_err());
    let mut cycle = nodes.clone();
    cycle[0].depends_on.push("decode".into());
    assert!(plan_incremental(&cycle, &BTreeMap::new(), &["decode".into()]).is_err());
}
