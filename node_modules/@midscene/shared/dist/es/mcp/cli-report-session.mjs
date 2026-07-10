import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { getMidsceneRunBaseDir, getMidsceneRunSubDir } from "../common.mjs";
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
    const dir = join(getMidsceneRunBaseDir(), sessionDirName);
    if (!existsSync(dir)) mkdirSync(dir, {
        recursive: true
    });
    return dir;
}
function getCliReportSessionPath(sessionName) {
    return join(getCliReportSessionDir(), `${sanitizeSessionName(sessionName)}.json`);
}
function generateCliReportSession(sessionName, targetIdentity) {
    const identitySegment = targetIdentity ? `-${sanitizeFileSegment(targetIdentity)}` : '';
    const reportFileName = `${sanitizeSessionName(sessionName)}${identitySegment}-${formatDateForFileName(new Date())}-${randomId()}`;
    const reportPath = join(getMidsceneRunSubDir('report'), ensureHtmlFileName(reportFileName));
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
    writeFileSync(getCliReportSessionPath(session.sessionName), JSON.stringify(session, null, 2), 'utf-8');
}
function createCliReportSession(sessionName, targetIdentity) {
    const session = generateCliReportSession(sessionName, targetIdentity);
    writeCliReportSession(session);
    return session;
}
function readCliReportSession(sessionName) {
    const sessionPath = getCliReportSessionPath(sessionName);
    if (!existsSync(sessionPath)) return;
    try {
        const raw = readFileSync(sessionPath, 'utf-8');
        const parsed = JSON.parse(raw);
        if (1 !== parsed.version || parsed.sessionName !== sessionName || 'string' != typeof parsed.reportFileName || !parsed.reportFileName.trim() || /[\\/]/.test(parsed.reportFileName)) return;
        return parsed;
    } catch  {
        return;
    }
}
export { createCliReportSession, generateCliReportSession, readCliReportSession, writeCliReportSession };
