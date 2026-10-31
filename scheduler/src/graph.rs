//! Deterministic DAG compiler. This is a plan, not the node execution engine.
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::error::Error;
use std::fmt::{self, Display};

#[derive(Clone, Debug, PartialEq, Eq, Deserialize, Serialize)]
pub struct NodeSpec {
    pub node_id: String,
    pub operation: String,
    #[serde(default)]
    pub depends_on: Vec<String>,
    #[serde(default)]
    pub components: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionPlan {
    /// Stable Kahn ordering, preserving the submitted order for independent nodes.
    pub order: Vec<String>,
    /// Last planned step requiring the output of each node.
    pub last_output_use: BTreeMap<String, usize>,
    /// Nodes that have no downstream consumers; return these to the caller.
    pub output_nodes: Vec<String>,
    /// Last step requiring each model component (advisory, NOT forced eviction).
    pub last_component_use: BTreeMap<String, usize>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SchedulerError(pub String);

impl Display for SchedulerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}
impl Error for SchedulerError {}

pub fn compile(nodes: &[NodeSpec]) -> Result<ExecutionPlan, SchedulerError> {
    let mut ids: HashMap<&str, usize> = HashMap::new();
    for (idx, node) in nodes.iter().enumerate() {
        if node.node_id.trim().is_empty() || node.operation.trim().is_empty() {
            return Err(SchedulerError("Node ID and operation cannot be empty".into()));
        }
        if ids.insert(&node.node_id, idx).is_some() {
            return Err(SchedulerError(format!("Duplicate node: {}", node.node_id)));
        }
        if node.components.iter().any(|key| key.trim().is_empty()) {
            return Err(SchedulerError(format!("Empty component key: {}", node.node_id)));
        }
    }

    let mut children: Vec<Vec<usize>> = vec![Vec::new(); nodes.len()];
    let mut indegree = vec![0usize; nodes.len()];
    for (idx, node) in nodes.iter().enumerate() {
        let mut unique_deps: HashSet<&str> = HashSet::new();
        for dependency in &node.depends_on {
            if !unique_deps.insert(dependency.as_str()) {
                continue;
            }
            let parent = ids.get(dependency.as_str()).ok_or_else(|| {
                SchedulerError(format!("{}: missing dependency {}", node.node_id, dependency))
            })?;
            children[*parent].push(idx);
            indegree[idx] += 1;
        }
    }

    let mut ready: VecDeque<usize> = (0..nodes.len()).filter(|idx| indegree[*idx] == 0).collect();
    let mut ordered: Vec<usize> = Vec::with_capacity(nodes.len());
    while let Some(index) = ready.pop_front() {
        ordered.push(index);
        for child in &children[index] {
            indegree[*child] -= 1;
            if indegree[*child] == 0 {
                ready.push_back(*child);
            }
        }
    }
    if ordered.len() != nodes.len() {
        return Err(SchedulerError("Graph has a dependency cycle".into()));
    }

    let mut index_by_id = BTreeMap::new();
    for (position, original) in ordered.iter().enumerate() {
        index_by_id.insert(nodes[*original].node_id.clone(), position);
    }
    let mut last_output_use = index_by_id.clone();
    let mut last_component_use = BTreeMap::new();
    for (position, original) in ordered.iter().enumerate() {
        let node = &nodes[*original];
        for parent in &node.depends_on {
            if let Some(last) = last_output_use.get_mut(parent) {
                *last = (*last).max(position);
            }
        }
        for component in &node.components {
            last_component_use.insert(component.clone(), position);
        }
    }
    let output_nodes = nodes.iter().enumerate()
        .filter(|(idx, _)| children[*idx].is_empty())
        .map(|(_, node)| node.node_id.clone())
        .collect();
    let order = ordered.iter().map(|idx| nodes[*idx].node_id.clone()).collect();
    Ok(ExecutionPlan { order, last_output_use, output_nodes, last_component_use })
}
