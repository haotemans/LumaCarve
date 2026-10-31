//! ComfyUI-inspired content signatures; derived independently, not ComfyUI code.
//! Cache identity ignores graph editor coordinates and parameter UI exposure.
use crate::graph::{compile, NodeSpec, SchedulerError};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FingerprintNode {
    pub node_id: String,
    pub operation: String,
    #[serde(default)]
    pub depends_on: Vec<String>,
    #[serde(default)]
    pub params: BTreeMap<String, Value>,
    /// Exact model revision or content digest, not just a display name.
    #[serde(default)]
    pub model_revision: Option<String>,
    /// SHA-256 of images or external resources in their semantically ordered sequence.
    #[serde(default)]
    pub asset_hashes: Vec<String>,
    /// Unique token for non-idempotent nodes. New token => forced recomputation.
    #[serde(default)]
    pub volatile_nonce: Option<String>,
    #[serde(default)]
    pub volatile: bool,
}

pub fn fingerprints(nodes: &[FingerprintNode]) -> Result<BTreeMap<String, String>, SchedulerError> {
    let specs: Vec<NodeSpec> = nodes.iter().map(|node| NodeSpec {
        node_id: node.node_id.clone(),
        operation: node.operation.clone(),
        depends_on: node.depends_on.clone(),
        components: vec![],
    }).collect();
    let plan = compile(&specs)?;
    let lookup: HashMap<&str, &FingerprintNode> =
        nodes.iter().map(|node| (node.node_id.as_str(), node)).collect();
    let mut known: BTreeMap<String, String> = BTreeMap::new();
    for id in plan.order {
        let node = lookup[&id.as_str()];
        if node.volatile && node.volatile_nonce.as_deref().unwrap_or("").is_empty() {
            return Err(SchedulerError(format!(
                "Non-deterministic node {id} requires volatile_nonce"
            )));
        }
        // Order is significant: image inputs, LoRA order and upstream positional
        // dependencies can all affect outputs. BTreeMap makes keys canonical.
        let upstream: Vec<_> = node.depends_on.iter().map(|parent| {
            json!({"input_node": parent, "fingerprint": known[parent]})
        }).collect();
        let signature = json!({
            "format": "lumacarve.cache.v1",
            "operation": node.operation,
            "params": node.params,
            "model_revision": node.model_revision,
            "assets": node.asset_hashes,
            "upstream": upstream,
            "nonce": node.volatile_nonce,
        });
        let bytes = serde_json::to_vec(&signature)
            .map_err(|err| SchedulerError(format!("Cache encoding error: {err}")))?;
        let hex_digest = format!("{:x}", Sha256::digest(bytes));
        known.insert(id, hex_digest);
    }
    Ok(known)
}
