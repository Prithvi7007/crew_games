# Frontend artifact synchronization

The development bridge should support a fixed operation to synchronize the generated React assets for a feature branch. It must only publish `app/static/react/player.js` and `app/static/react/player.css` after a successful reproducible frontend build. It must not deploy production, write to main, or accept arbitrary command arguments.

The implementation should run in the isolated development runner, check the branch and build results, and commit the generated files to the same feature branch. A failed build must not publish anything.

## Integration requirement

This module is a proposed trusted-runner implementation, not an activated MCP tool. The separately deployed `crew-dev-bridge` service must be updated in a reviewed change to call `synchronize_frontend_assets` from its isolated runner, expose a fixed zero-argument tool, and ensure its Git credentials can push only the feature branch. The currently installed bridge does not expose this function. Do not run this module on the production CREW checkout.
