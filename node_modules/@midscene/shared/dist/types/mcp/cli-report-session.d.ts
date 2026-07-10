export interface CliReportSession {
    version: 1;
    sessionName: string;
    targetIdentity?: string;
    reportFileName: string;
    reportPath: string;
    createdAt: number;
}
export declare function generateCliReportSession(sessionName: string, targetIdentity?: string): CliReportSession;
export declare function writeCliReportSession(session: CliReportSession): void;
export declare function createCliReportSession(sessionName: string, targetIdentity?: string): CliReportSession;
export declare function readCliReportSession(sessionName: string): CliReportSession | undefined;
