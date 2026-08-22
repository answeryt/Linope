# Allow list

## paths

- `tools/external_tools/ci_tools/generate/serve_generate`
- `tools/external_tools/ci_tools/generate/session_generate`
- `tools/external_tools/ci_tools/generate/third_party_generate.py`

## inject

- `message_tokens`: `text_estimator`
- `process_lifecycle`: `table`, `transition`, `build_pcb`
- `thred_lifecycle`: `table`, `transition`, `build_thread`
- `runtime`: `create_process`, `create_task`, `gather`, `emit`, `loop`, `scheduler`
- `event_loop`: `bus`
- `dispatch`: `call_model`, `call_tool`, `emit`
- `usecase`: `agent_loop`
- `app`: `application`
- `stream_subscriber`: `consume`

## kernel_layers

- `services`: `app`, `broker`, `entry`, `middleware`, `task`
- `process`: `pcb`, `lifecycle`, `state`, `resource`, `table`
- `async`: `runtime`, `scheduler`, `execution`, `event`, `dispatch`
- `thred`: `context`, `lifecycle`, `state`, `table`, `wait`

## kernel_loops

- `agent`: `kernel/services/task/loop_plugin.py`
- `dispatch`: `kernel/async/dispatch/dispatch_plugin.py`
- `event`: `kernel/async/event/event_loop_plugin.py`
