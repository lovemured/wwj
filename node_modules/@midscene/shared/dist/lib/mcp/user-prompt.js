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
    promptInputExtraSchema: ()=>promptInputExtraSchema,
    composeUserPrompt: ()=>composeUserPrompt
});
const external_zod_namespaceObject = require("zod");
function normalizeStringList(raw, fieldName) {
    if (null == raw) return [];
    if ('string' == typeof raw) {
        const trimmed = raw.trim();
        return trimmed ? [
            trimmed
        ] : [];
    }
    if (Array.isArray(raw)) return raw.map((item, index)=>{
        if ('string' != typeof item) throw new Error(`${fieldName}[${index}]: expected a string.`);
        return item.trim();
    });
    throw new Error(`${fieldName}: expected a string or string array, got ${typeof raw}.`);
}
function composeImages(input) {
    const urls = normalizeStringList(input.image, 'image');
    const names = normalizeStringList(input.imageName, 'imageName');
    if (urls.length !== names.length) throw new Error(`image/imageName: expected the same number of --image and --image-name values, got ${urls.length} image(s) and ${names.length} image name(s).`);
    return urls.map((url, index)=>({
            name: names[index],
            url
        }));
}
function coerceBoolean(value) {
    if (null == value) return;
    if ('boolean' == typeof value) return value;
    if ('string' == typeof value) {
        const trimmed = value.trim();
        if (!trimmed) return;
        const v = trimmed.toLowerCase();
        if ('true' === v || '1' === v) return true;
        if ('false' === v || '0' === v) return false;
        throw new Error(`convertHttpImage2Base64: expected "true", "false", "1", or "0"; got ${JSON.stringify(value)}.`);
    }
    throw new Error(`convertHttpImage2Base64: expected a boolean, got ${typeof value}.`);
}
function composeUserPrompt(input) {
    const images = composeImages({
        image: input.image,
        imageName: input.imageName
    });
    const convertFlag = coerceBoolean(input.convertHttpImage2Base64);
    if (0 === images.length && void 0 === convertFlag) return input.prompt;
    const payload = {
        prompt: input.prompt
    };
    if (images.length > 0) payload.images = images;
    if (void 0 !== convertFlag) payload.convertHttpImage2Base64 = convertFlag;
    return payload;
}
const promptInputExtraSchema = {
    image: external_zod_namespaceObject.z.union([
        external_zod_namespaceObject.z.string(),
        external_zod_namespaceObject.z.array(external_zod_namespaceObject.z.string())
    ]).optional().describe('Reference image URL/path. Repeat --image for multiple images.'),
    imageName: external_zod_namespaceObject.z.union([
        external_zod_namespaceObject.z.string(),
        external_zod_namespaceObject.z.array(external_zod_namespaceObject.z.string())
    ]).optional().describe('Reference image name. Repeat --image-name; must align with --image order.'),
    convertHttpImage2Base64: external_zod_namespaceObject.z.union([
        external_zod_namespaceObject.z.boolean(),
        external_zod_namespaceObject.z.string()
    ]).optional().describe('If true, convert http(s) image URLs to base64 before sending to the model.')
};
exports.composeUserPrompt = __webpack_exports__.composeUserPrompt;
exports.promptInputExtraSchema = __webpack_exports__.promptInputExtraSchema;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "composeUserPrompt",
    "promptInputExtraSchema"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});
