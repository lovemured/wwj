"use strict";
var __webpack_require__ = {};
(()=>{
    __webpack_require__.d = (exports1, definition)=>{
        for(var key in definition)if (__webpack_require__.o(definition, key) && !__webpack_require__.o(exports1, key)) Object.defineProperty(exports1, key, {
            enumerable: true,
            get: definition[key]
        });
    };
})();
(()=>{
    __webpack_require__.o = (obj, prop)=>Object.prototype.hasOwnProperty.call(obj, prop);
})();
(()=>{
    __webpack_require__.r = (exports1)=>{
        if ('undefined' != typeof Symbol && Symbol.toStringTag) Object.defineProperty(exports1, Symbol.toStringTag, {
            value: 'Module'
        });
        Object.defineProperty(exports1, '__esModule', {
            value: true
        });
    };
})();
var __webpack_exports__ = {};
__webpack_require__.r(__webpack_exports__);
__webpack_require__.d(__webpack_exports__, {
    validateAgentCacheInput: ()=>validateAgentCacheInput
});
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
exports.validateAgentCacheInput = __webpack_exports__.validateAgentCacheInput;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "validateAgentCacheInput"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});

//# sourceMappingURL=cache-config.js.map