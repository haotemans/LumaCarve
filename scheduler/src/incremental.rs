//! Output-directed incremental Graph planning, inspired by ComfyUI principles.
//!
//! A cache hit means Python guarantees that the complete intermediate output
//! is still available. Hash matches without available data are not cache hits.
use crate::cache::{fingerprints, FingerprintNode};
use crate::graph::{compile, NodeSpec, SchedulerError};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap, HashSet};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct CachedOutput {
    pub fingerprint: String,
    pub available: bool,
}

#[derive(Copy, Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StepAction {
    Execute,
    Reuse,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct IncrementalStep {
    pub node_id: String,
    pub fingerprint: String,
    pub action: StepAction,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct IncrementalPlan {
    pub requested_outputs: Vec<String>,
    pub steps: Vec<IncrementalStep>,
    pub executed: usize,
    pub reused: usize,
}

fn reusable(
    node: &FingerprintNode,
    fingerprint: &str,
    known: &BTreeMap<String, CachedOutput>,
) -> bool {
    if node.volatile {
        return false;
    }
    known.get(&node.node_id).is_some_and(|entry|
        entry.available && entry.fingerprint == fingerprint
    )
}

fn include_dependencies(
    id: &str,
    lookup: &HashMap<&str, &FingerprintNode>,
    fingerprints: &BTreeMap<String, String>,
    known: &BTreeMap<String, CachedOutput>,
    included: &mut HashSet<String>,
) {
    if !included.insert(id.to_string()) {
        return;
    }
    let node = lookup[id];
    if reusable(node, &fingerprints[id], known) {
        // Cached outputs cut off upstream traversal: no repeated text encode.
        return;
    }
    for parent in &node.depends_on {
        include_dependencies(parent, lookup, fingerprints, known, included);
    }
}

/// Compile a minimal plan for requested output node IDs.
///
/// This plans metadata only. Python is responsible for cache object validity,
/// model execution, tensor lifetimes and observed memory pressure.
pub fn plan_incremental(
    nodes: &[FingerprintNode],
    known: &BTreeMap<String, CachedOutput>,
    requested_outputs: &[String],
) -> Result<IncrementalPlan, SchedulerError> {
    let specs: Vec<NodeSpec> = nodes.iter().map(|node| NodeSpec {
        node_id: node.node_id.clone(),
        operation: node.operation.clone(),
        depends_on: node.depends_on.clone(),
        components: vec![],
    }).collect();
    let topology = compile(&specs)?;
    let signatures = fingerprints(nodes)?;
    let lookup: HashMap<&str, &FingerprintNode> =
        nodes.iter().map(|node| (node.node_id.as_str(), node)).collect();
    let roots = if requested_outputs.is_empty() {
        topology.output_nodes
    } else {
        requested_outputs.to_vec()
    };
    for root in &roots {
        if !lookup.contains_key(root.as_str()) {
            return Err(SchedulerError(format!("Unknown requested output: {root}")));
        }
    }
    let mut included = HashSet::new();
    for root in &roots {
        include_dependencies(root, &lookup, &signatures, known, &mut included);
    }
    let mut steps = Vec::new();
    let mut executed = 0;
    let mut reused = 0;
    for id in topology.order {
        if !included.contains(&id) {
            continue;
        }
        let node = lookup[id.as_str()];
        let signature = &signatures[&id];
        let action = if reusable(node, signature, known) {
            reused += 1;
            StepAction::Reuse
        } else {
            executed += 1;
            StepAction::Execute
        };
        steps.push(IncrementalStep {
            node_id: id, fingerprint: signature.clone(), action
        });
    }
    Ok(IncrementalPlan {
        requested_outputs: roots,
        steps,
        executed,
        reused,
    })
}
