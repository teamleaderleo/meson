# Meson 15998 execution receipt

- Workflow run: https://github.com/teamleaderleo/meson/actions/runs/30858277753
- Starting packet head: 35ae8c752b0075bd1ef5ee1c443c840d185c446f
- Before source edit: focused synthetic CUDA standard regression failed as expected.
- After source edit: focused regression passed.
- Python compileall and git diff --check passed.
- Runner: Ubuntu 24.04.
- Evidence class: compiler-free target-executed source classification and deduplication.
- Precedence among CMake-discovered standards, project cuda_std, and explicit subproject overrides remains unproven.
- External contact: none; unauthorized.
