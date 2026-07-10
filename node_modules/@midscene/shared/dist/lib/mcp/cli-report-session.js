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
    createCliReportSession: ()=>createCliReportSession,
    generateCliReportSession: ()=>generateCliReportSession,
    readCliReportSession: ()=>readCliReportSession,
    writeCliReportSession: ()=>writeCliReportSession
});
const external_node_fs_namespaceObject = require("node:fs");
const external_node_path_namespaceObject = require("node:path");
const external_common_js_namespaceObject = require("../common.js");
const sessionDirName = 'cli-report-session';
function sanitizeSessionName(sessionName) {
    return sessionName.replace(/[^a-zA-Z0-9._-]/g, '_') || 'default';
}
function sanitizeFileSegment(segment) {
    const sanitized = segment.replace(/[^a-zA-Z0-9._-]/g, '_') || 'unknown';
    return sanitized.slice(0, 80);
}
function ensureHtmlFileName(reportFileName) {
    return reportFileName.endsWith('.html') ? reportFileName : `${reportFileName}.html`;
}
function formatDateForFileName(date) {
    const pad = (value)=>String(value).padStart(2, '0');
    const day = [
        date.getFullYear(),
        pad(date.getMonth() + 1),
        pad(date.getDate())
    ].join('-');
    const time = [
        pad(date.getHours()),
        pad(date.getMinutes()),
        pad(date.getSeconds())
    ].join('-');
    return `${day}_${time}`;
}
function randomId() {
    return Math.random().toString(36).slice(2, 10);
}
function getCliReportSessionDir() {
    const dir = (0, external_node_path_namespaceObject.join)((0, external_common_js_namespaceObject.getMidsceneRunBaseDir)(), sessionDirName);
    if (!(0, external_node_fs_namespaceObject.existsSync)(dir)) (0, external_node_fs_namespaceObject.mkdirSync)(dir, {
        recursive: true
    });
    return dir;
}
function getCliReportSessionPath(sessionName) {
    return (0, external_node_path_namespaceObject.join)(getCliReportSessionDir(), `${sanitizeSessionName(sessionName)}.json`);
}
function generateCliReportSession(sessionName, targetIdentity) {
    const identitySegment = targetIdentity ? `-${sanitizeFileSegment(targetIdentity)}` : '';
    const reportFileName = `${sanitizeSessionName(sessionName)}${identitySegment}-${formatDateForFileName(new Date())}-${randomId()}`;
    const reportPath = (0, external_node_path_namespaceObject.join)((0, external_common_js_namespaceObject.getMidsceneRunSubDir)('report'), ensureHtmlFileName(reportFileName));
    const session = {
        version: 1,
        sessionName,
        ...targetIdentity ? {
            targetIdentity
        } : {},
        reportFileName,
        reportPath,
        createdAt: Date.now()
    };
    return session;
}
function writeCliReportSession(session) {
    (0, external_node_fs_namespaceObject.writeFileSync)(getCliReportSessionPath(session.sessionName), JSON.stringify(session, null, 2), 'utf-8');
}
function createCliReportSession(sessionName, targetIdentity) {
    const session = generateCliReportSession(sessionName, targetIdentity);
    writeCliReportSession(session);
    return session;
}
function readCliReportSession(sessionName) {
    const sessionPath = getCliReportSessionPath(sessionName);
    if (!(0, external_node_fs_namespaceObject.existsSync)(sessionPath)) return;
    try {
        const raw = (0, external_node_fs_namespaceObject.readFileSync)(sessionPath, 'utf-8');
        const parsed = JSON.parse(raw);
        if (1 !== parsed.version || parsed.sessionName !== sessionName || 'string' != typeof parsed.reportFileName || !parsed.reportFileName.trim() || /[\\/]/.test(parsed.reportFileName)) return;
        return parsed;
    } catch  {
        return;
    }
}
exports.createCliReportSession = __webpack_exports__.createCliReportSession;
exports.generateCliReportSession = __webpack_exports__.generateCliReportSession;
exports.readCliReportSession = __webpack_exports__.readCliReportSession;
exports.writeCliReportSession = __webpack_exports__.writeCliReportSession;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "createCliReportSession",
    "generateCliReportSession",
    "readCliReportSession",
    "writeCliReportSession"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});
