const CACHE_STRATEGIES = [
    'read-only',
    'read-write',
    'write-only'
];
const isValidCacheStrategy = (strategy)=>CACHE_STRATEGIES.some((value)=>value === strategy);
const CACHE_STRATEGY_VALUES = CACHE_STRATEGIES.map((value)=>`"${value}"`).join(', ');
function validateAgentCacheInput(cache) {
    if (true === cache) throw new Error('cache: true requires an explicit cache ID. Please provide:\nExample: cache: { id: "my-cache-id" }');
    if (!cache || 'object' != typeof cache) return;
    if (!cache.id) throw new Error('cache configuration requires an explicit id.\nExample: cache: { id: "my-cache-id" }');
    if (void 0 !== cache.cacheDir && ('string' != typeof cache.cacheDir || !cache.cacheDir.trim())) throw new Error('cache.cacheDir must be a non-empty string when provided.\nExample: cache: { id: "my-cache-id", cacheDir: "./my-cache-dir" }');
    const rawStrategy = cache.strategy;
    if (void 0 !== rawStrategy && 'string' != typeof rawStrategy) throw new Error(`cache.strategy must be a string when provided, but received type ${typeof rawStrategy}`);
    if (void 0 !== rawStrategy && !isValidCacheStrategy(rawStrategy)) throw new Error(`cache.strategy must be one of ${CACHE_STRATEGY_VALUES}, but received "${rawStrategy}"`);
}
export { validateAgentCacheInput };

//# sourceMappingURL=cache-config.mjs.map