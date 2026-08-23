# Allow list

## paths

- `tools/external_tools/ci_tools/generate/serve_generate`
- `tools/external_tools/ci_tools/generate/session_generate`
- `tools/external_tools/ci_tools/generate/third_party_generate.py`

## inject

- `message_tokens`: `text_estimator`
- `process_lifecycle`: `store`, `transition`, `build_process_run`
- `process_runtime`: `processes`, `store`, `journal`, `lifecycle`
- `process_worker`: `queue`, `runtime`
- `usecase`: `runtime`
- `app`: `application`
- `stream_subscriber`: `consume`
- `sandbox_policy`: `canonical_path`, `effective_mode`
- `sandbox_policy_plugin`: `canonical_path`, `effective_mode`
- `sandbox_local`: `bwrap_profile_args`, `landlock_profile_args`, `seatbelt_profile_args`
- `sandbox_local_plugin`: `bwrap_profile_args`, `landlock_profile_args`, `seatbelt_profile_args`
- `sandbox_profiles`: `writable_roots`
- `profiles_plugin`: `writable_roots`

## kernel_layers

- `services`: `app`, `ingress`, `worker`, `queue`, `store`
- `process`: `activation`, `definition`, `runtime`, `journal`, `lifecycle`, `state`, `handle`
- `thred`: `binding`, `definition`, `executor`
- `resource`: `definition`, `pool`
