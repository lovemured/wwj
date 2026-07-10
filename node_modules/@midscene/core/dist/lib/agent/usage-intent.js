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
    withUsageIntent: ()=>withUsageIntent
});
const logger_namespaceObject = require("@midscene/shared/logger");
const warnUsageIntent = (0, logger_namespaceObject.getDebug)('agent:usage-intent', {
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
exports.withUsageIntent = __webpack_exports__.withUsageIntent;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "withUsageIntent"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});

//# sourceMappingURL=usage-intent.js.map