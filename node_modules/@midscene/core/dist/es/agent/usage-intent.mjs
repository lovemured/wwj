import { getDebug } from "@midscene/shared/logger";
const warnUsageIntent = getDebug('agent:usage-intent', {
    console: true
});
function withUsageIntent(usage, intent) {
    if (!usage) return;
    if (usage.intent) {
        warnUsageIntent(`intent is already set to "${usage.intent}", skipping overwrite to "${intent}"`);
        return usage;
    }
    return {
        ...usage,
        intent
    };
}
export { withUsageIntent };

//# sourceMappingURL=usage-intent.mjs.map