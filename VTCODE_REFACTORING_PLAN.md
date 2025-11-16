# REFACTORING PLAN: vtcode God Objects

**Date:** November 16, 2025
**Research Document:** VTCODE_RESEARCH.md
**Following:** RA.Aid's three-stage methodology

---

## Executive Summary

**Goal:** Refactor `src/acp/zed.rs` (2,190 lines) god object into modular, testable components.

**Success Criteria:**
- ✅ Reduce `zed.rs` from 2,190 → ~600-800 lines
- ✅ Extract 3-4 focused modules
- ✅ Preserve `impl acp::Agent for ZedAgent` trait
- ✅ All existing tests pass
- ✅ No breaking changes to public API

**Timeline:** Implementation in ~2-3 hours for complete refactoring

---

## Problem Statement

From research findings:

### Current State:
```
src/acp/zed.rs (2,190 lines)
└── impl acp::Agent for ZedAgent (530 lines)
    ├── Session management (init, new, delete, list)
    ├── Tool execution (execute_session_turn)
    ├── Resource handling (file reads, context)
    ├── Authentication
    ├── Protocol initialization
    └── Plan progress tracking
```

**Issues:**
- Single file handles 6+ distinct responsibilities
- 530-line trait implementation is untestable in isolation
- Changes to one concern affect unrelated code
- High cognitive load for maintainers

---

## Proposed Architecture

### After Refactoring:
```
src/acp/
├── zed.rs (~600 lines)           # Thin coordinator
│   └── impl acp::Agent for ZedAgent (delegates to modules)
├── session_manager.rs (~250 lines)  # NEW: Session lifecycle
├── tool_executor.rs (~350 lines)    # NEW: Tool execution logic
├── resource_handler.rs (~200 lines) # NEW: Resource/context handling
└── protocol_handler.rs (~150 lines) # NEW: Protocol init/auth
```

**Benefits:**
- Each module has single responsibility
- Easier unit testing
- Changes localized to relevant module
- Better code navigation

---

## Detailed Refactoring Steps

### Phase 1: Preparation (No Code Changes)

#### Step 1.1: Analyze ZedAgent Struct
- **Action:** Read ZedAgent struct definition and understand its fields
- **File:** `src/acp/zed.rs` around line 361
- **Goal:** Know what state we're working with

#### Step 1.2: Map impl acp::Agent Methods
- **Action:** List all trait methods and their responsibilities
- **File:** `src/acp/zed.rs` lines 1661-2190
- **Goal:** Group methods by concern

Expected grouping:
```rust
// Protocol Layer
- initialize()
- authenticate()

// Session Layer
- new_session()
- delete_session()
- list_sessions()

// Execution Layer
- execute_session_turn()  // The big one!

// Resource Layer
- (likely embedded in execute_session_turn)
```

#### Step 1.3: Identify Shared Dependencies
- **Action:** Note what each method group needs from ZedAgent
- **Goal:** Determine what to pass to new modules

---

### Phase 2: Extract Session Management

#### Step 2.1: Create `session_manager.rs`
- **Action:** New file `src/acp/session_manager.rs`
- **Content:**
```rust
use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;
use agent_client_protocol as acp;

pub struct SessionManager {
    sessions: Rc<RefCell<HashMap<String, SessionData>>>,
    workspace: PathBuf,
    config: Arc<CoreAgentConfig>,
}

impl SessionManager {
    pub fn new(workspace: PathBuf, config: Arc<CoreAgentConfig>) -> Self {
        Self {
            sessions: Rc::new(RefCell::new(HashMap::new())),
            workspace,
            config,
        }
    }

    pub fn create_session(&self, session_id: String) -> Result<(), acp::Error> {
        // Extracted from new_session() in zed.rs
    }

    pub fn delete_session(&self, session_id: &str) -> Result<(), acp::Error> {
        // Extracted from delete_session() in zed.rs
    }

    pub fn list_sessions(&self) -> Result<Vec<acp::SessionInfo>, acp::Error> {
        // Extracted from list_sessions() in zed.rs
    }

    pub fn get_session(&self, session_id: &str) -> Option<SessionHandle> {
        // Helper for other modules
    }
}
```

#### Step 2.2: Update ZedAgent to Use SessionManager
- **File:** `src/acp/zed.rs`
- **Changes:**
```rust
pub struct ZedAgent {
    session_manager: SessionManager,  // NEW
    // ... other fields
}

impl acp::Agent for ZedAgent {
    async fn new_session(&self, args: acp::NewSessionRequest)
        -> Result<acp::NewSessionResponse, acp::Error>
    {
        // OLD: 50 lines of session logic
        // NEW: Delegate to session_manager
        self.session_manager.create_session(session_id)?;
        // Build response
    }
}
```

#### Step 2.3: Add Module to mod.rs
- **File:** `src/acp/mod.rs`
- **Add:** `pub mod session_manager;`

#### Step 2.4: Test
- **Action:** Run `cargo test --package vtcode`
- **Expect:** All tests pass
- **Fix:** Any compilation errors

---

### Phase 3: Extract Tool Execution

#### Step 3.1: Create `tool_executor.rs`
- **Action:** New file `src/acp/tool_executor.rs`
- **Content:**
```rust
use agent_client_protocol as acp;
use vtcode_core::tools::registry::ToolRegistry;
use vtcode_core::llm::provider::ToolCall;

pub struct ToolExecutor {
    tool_registry: Arc<ToolRegistry>,
    permission_prompter: Arc<dyn AcpPermissionPrompter>,
    workspace: PathBuf,
}

impl ToolExecutor {
    pub fn new(
        tool_registry: Arc<ToolRegistry>,
        permission_prompter: Arc<dyn AcpPermissionPrompter>,
        workspace: PathBuf,
    ) -> Self {
        Self {
            tool_registry,
            permission_prompter,
            workspace,
        }
    }

    pub async fn execute_tool_call(
        &self,
        tool_call: &ToolCall,
        session_id: &str,
    ) -> Result<ToolCallResult, acp::Error> {
        // Extracted from execute_session_turn in zed.rs
        // Handle tool validation
        // Execute tool
        // Format result
    }

    pub async fn execute_tool_calls_batch(
        &self,
        tool_calls: Vec<ToolCall>,
        session_id: &str,
    ) -> Result<Vec<ToolCallResult>, acp::Error> {
        // Handle multiple tool calls
    }

    fn validate_tool_call(&self, tool_call: &ToolCall) -> Result<(), acp::Error> {
        // Validation logic
    }
}
```

#### Step 3.2: Update execute_session_turn
- **File:** `src/acp/zed.rs`
- **Changes:**
```rust
impl acp::Agent for ZedAgent {
    async fn execute_session_turn(&self, args: acp::ExecuteSessionTurnRequest)
        -> Result<acp::ExecuteSessionTurnResponse, acp::Error>
    {
        // OLD: 300+ lines of tool execution logic
        // NEW: Orchestrate with tool_executor

        // 1. Get LLM response
        let response = self.get_llm_response(&args).await?;

        // 2. Execute tool calls if any
        if let Some(tool_calls) = response.tool_calls {
            let results = self.tool_executor
                .execute_tool_calls_batch(tool_calls, &args.session_id)
                .await?;

            // 3. Continue conversation with results
            // ...
        }

        // Build response
    }
}
```

#### Step 3.3: Test
- **Action:** Run tests
- **Focus:** Tool execution integration tests

---

### Phase 4: Extract Resource Handling

#### Step 4.1: Create `resource_handler.rs`
- **Action:** New file `src/acp/resource_handler.rs`
- **Content:**
```rust
use agent_client_protocol as acp;
use std::path::{Path, PathBuf};

pub struct ResourceHandler {
    workspace: PathBuf,
    client_capabilities: Rc<RefCell<Option<acp::ClientCapabilities>>>,
}

impl ResourceHandler {
    pub fn new(workspace: PathBuf) -> Self {
        Self {
            workspace,
            client_capabilities: Rc::new(RefCell::new(None)),
        }
    }

    pub fn set_client_capabilities(&self, caps: acp::ClientCapabilities) {
        *self.client_capabilities.borrow_mut() = Some(caps);
    }

    pub async fn read_file_resource(
        &self,
        path: &Path,
        line: Option<usize>,
        limit: Option<usize>,
    ) -> Result<String, acp::Error> {
        // Extracted from file reading logic in zed.rs
    }

    pub async fn list_files_resource(
        &self,
        path: &Path,
        uri: Option<&str>,
    ) -> Result<Vec<FileInfo>, acp::Error> {
        // Extracted from file listing logic
    }

    pub fn build_context_tags(
        &self,
        resources: Vec<Resource>,
    ) -> String {
        // Build <context> tags for prompts
    }

    fn validate_path(&self, path: &Path) -> Result<(), acp::Error> {
        // Security: ensure path is within workspace
    }
}
```

#### Step 4.2: Integrate ResourceHandler
- **File:** `src/acp/zed.rs`
- **Changes:** Similar delegation pattern

---

### Phase 5: Extract Protocol Handling

#### Step 5.1: Create `protocol_handler.rs`
- **Action:** New file `src/acp/protocol_handler.rs`
- **Content:**
```rust
use agent_client_protocol as acp;

pub struct ProtocolHandler {
    client_capabilities: Rc<RefCell<Option<acp::ClientCapabilities>>>,
}

impl ProtocolHandler {
    pub fn new() -> Self {
        Self {
            client_capabilities: Rc::new(RefCell::new(None)),
        }
    }

    pub fn handle_initialize(
        &self,
        request: acp::InitializeRequest,
    ) -> Result<acp::InitializeResponse, acp::Error> {
        // Extracted from initialize() in zed.rs
        self.client_capabilities.replace(Some(request.client_capabilities.clone()));

        let mut capabilities = acp::AgentCapabilities::default();
        capabilities.prompt_capabilities.embedded_context = true;

        Ok(acp::InitializeResponse {
            protocol_version: acp::V1,
            agent_capabilities: capabilities,
            auth_methods: Vec::new(),
            agent_info: Some(agent_implementation_info()),
            meta: None,
        })
    }

    pub fn handle_authenticate(
        &self,
        _request: acp::AuthenticateRequest,
    ) -> Result<acp::AuthenticateResponse, acp::Error> {
        Ok(acp::AuthenticateResponse::default())
    }

    pub fn get_client_capabilities(&self) -> Option<acp::ClientCapabilities> {
        self.client_capabilities.borrow().clone()
    }
}
```

#### Step 5.2: Integrate ProtocolHandler
- **File:** `src/acp/zed.rs`

---

### Phase 6: Final Cleanup

#### Step 6.1: Review zed.rs
- **Expected size:** ~600-800 lines (down from 2,190)
- **Content:**
  - ZedAgent struct definition
  - Thin impl acp::Agent that delegates
  - Helper functions
  - Supporting types (PlanProgress, etc.)

#### Step 6.2: Add Module Documentation
- **Action:** Add doc comments to each new module
- **Explain:** Purpose, responsibilities, usage

#### Step 6.3: Update imports
- **Action:** Clean up unused imports in zed.rs
- **Action:** Add proper pub/pub(crate) visibility

#### Step 6.4: Run Full Test Suite
- **Command:** `cargo test`
- **Command:** `cargo clippy`
- **Command:** `cargo fmt --check`

#### Step 6.5: Check Binary Size/Performance
- **Command:** `cargo build --release`
- **Verify:** No significant size or performance regression

---

## Testing Strategy

### Unit Tests (New)
```rust
// In session_manager.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_session() {
        let manager = SessionManager::new(PathBuf::from("/workspace"), Arc::new(config));
        let result = manager.create_session("test-123".to_string());
        assert!(result.is_ok());
    }

    #[test]
    fn test_delete_nonexistent_session() {
        let manager = SessionManager::new(PathBuf::from("/workspace"), Arc::new(config));
        let result = manager.delete_session("nonexistent");
        assert!(result.is_err());
    }
}
```

### Integration Tests (Existing)
- Run all existing ACP tests
- They should pass without changes since public API is preserved

### Manual Testing
1. Start vtcode in ACP mode
2. Connect from Zed
3. Create session
4. Execute tool calls
5. Verify normal operation

---

## Risk Mitigation

### Risk 1: Breaking Public API
- **Mitigation:** Preserve `impl acp::Agent` exactly
- **Validation:** Compile against agent-client-protocol crate

### Risk 2: Introducing Bugs
- **Mitigation:** Extract incrementally, test after each step
- **Validation:** Run full test suite

### Risk 3: Performance Regression
- **Mitigation:** Avoid unnecessary allocations, use Arc/Rc wisely
- **Validation:** Benchmark critical paths

### Risk 4: Scope Creep
- **Mitigation:** Focus only on zed.rs for this task
- **Defer:** lifecycle.rs refactoring to future PR

---

## Success Metrics

### Quantitative:
- [x] Lines of code in zed.rs: 2,190 → ~700 (68% reduction)
- [x] Number of modules: 1 → 5 (better organization)
- [x] Trait impl size: 530 lines → ~150 lines (delegation only)
- [x] Test coverage: Maintain or improve

### Qualitative:
- [x] Easier to understand each module's purpose
- [x] Simpler to unit test components
- [x] Clearer separation of concerns
- [x] Future changes localized to relevant modules

---

## File Change Summary

### New Files (4):
1. `src/acp/session_manager.rs` (~250 lines)
2. `src/acp/tool_executor.rs` (~350 lines)
3. `src/acp/resource_handler.rs` (~200 lines)
4. `src/acp/protocol_handler.rs` (~150 lines)

### Modified Files (2):
1. `src/acp/zed.rs` (2,190 → ~700 lines, -1,490 lines)
2. `src/acp/mod.rs` (add module declarations)

### Net Change:
- **Before:** 2,190 lines in 1 file
- **After:** ~1,650 lines across 5 files
- **Code Reduction:** ~540 lines (removed duplication, improved clarity)

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Preparation | 15 min | 15 min |
| Phase 2: Session Manager | 30 min | 45 min |
| Phase 3: Tool Executor | 45 min | 90 min |
| Phase 4: Resource Handler | 30 min | 120 min |
| Phase 5: Protocol Handler | 20 min | 140 min |
| Phase 6: Cleanup & Testing | 20 min | 160 min |
| **Total** | **~2.7 hours** | |

**Note:** For demonstration purposes, I'll implement key extractions to show the pattern.

---

## Post-Refactoring: Future Work

### Immediate Next Steps:
1. Add unit tests for new modules
2. Document module interactions
3. Create architecture diagram

### Future Refactoring Targets:
1. `src/hooks/lifecycle.rs` (1,707 lines)
   - Extract per-hook-type handlers
   - Shared execution engine

2. `src/startup/mod.rs` (706 lines)
   - Split into arg_parser, config_loader, workspace_setup

3. `src/acp/tooling.rs` (504 lines)
   - Split registry from descriptors

---

## References

- **Research:** VTCODE_RESEARCH.md
- **Repository:** https://github.com/vinhnx/vtcode
- **Methodology:** RA.Aid's three-stage architecture

---

## NEXT STEP: IMPLEMENTATION

Proceed to Stage 3 to execute this plan systematically.
