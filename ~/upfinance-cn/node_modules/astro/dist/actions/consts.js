const VIRTUAL_MODULE_ID = "astro:actions";
const RESOLVED_VIRTUAL_MODULE_ID = "\0" + VIRTUAL_MODULE_ID;
const ACTIONS_TYPES_FILE = "astro/actions.d.ts";
const VIRTUAL_INTERNAL_MODULE_ID = "astro:internal-actions";
const RESOLVED_VIRTUAL_INTERNAL_MODULE_ID = "\0astro:internal-actions";
const NOOP_ACTIONS = "\0noop-actions";
const ACTION_QUERY_PARAMS = {
  actionName: "_astroAction",
  actionPayload: "_astroActionPayload",
  actionRedirect: "_astroActionRedirect"
};
export {
  ACTIONS_TYPES_FILE,
  ACTION_QUERY_PARAMS,
  NOOP_ACTIONS,
  RESOLVED_VIRTUAL_INTERNAL_MODULE_ID,
  RESOLVED_VIRTUAL_MODULE_ID,
  VIRTUAL_INTERNAL_MODULE_ID,
  VIRTUAL_MODULE_ID
};
