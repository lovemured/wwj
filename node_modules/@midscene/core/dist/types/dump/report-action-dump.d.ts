import { ScreenshotItem } from '../screenshot-item';
import type { ExecutionTask, IExecutionDump, IReportActionDump } from '../types';
/**
 * ExecutionDump class for serializing and deserializing execution dumps
 */
export declare class ExecutionDump implements IExecutionDump {
    id?: string;
    logTime: number;
    name: string;
    description?: string;
    tasks: ExecutionTask[];
    aiActContext?: string;
    constructor(data: IExecutionDump);
    /**
     * Serialize the ExecutionDump to a JSON string
     */
    serialize(indents?: number): string;
    /**
     * Convert to a plain object for JSON serialization
     */
    toJSON(): IExecutionDump;
    /**
     * Create an ExecutionDump instance from a serialized JSON string
     */
    static fromSerializedString(serialized: string): ExecutionDump;
    /**
     * Create an ExecutionDump instance from a plain object
     */
    static fromJSON(data: IExecutionDump): ExecutionDump;
    /**
     * Collect all ScreenshotItem instances from tasks.
     * Scans through uiContext and recorder items to find screenshots.
     *
     * @returns Array of ScreenshotItem instances
     */
    collectScreenshots(): ScreenshotItem[];
}
/**
 * ReportActionDump class for serializing and deserializing report action dumps
 */
export declare class ReportActionDump implements IReportActionDump {
    sdkVersion: string;
    groupName: string;
    groupDescription?: string;
    modelBriefs: IReportActionDump['modelBriefs'];
    executions: ExecutionDump[];
    deviceType?: string;
    constructor(data: IReportActionDump);
    /**
     * Serialize the ReportActionDump to a JSON string
     * Uses compact { $screenshot: id } format
     */
    serialize(indents?: number): string;
    /**
     * Serialize the ReportActionDump with inline screenshots to a JSON string.
     * Each ScreenshotItem is replaced with { base64: "...", capturedAt }.
     */
    serializeWithInlineScreenshots(indents?: number): string;
    /**
     * Convert to a plain object for JSON serialization
     */
    toJSON(): IReportActionDump;
    /**
     * Create a ReportActionDump instance from a serialized JSON string
     */
    static fromSerializedString(serialized: string): ReportActionDump;
    /**
     * Create a ReportActionDump instance from a plain object
     */
    static fromJSON(data: IReportActionDump): ReportActionDump;
    /**
     * Collect all ScreenshotItem instances from all executions.
     *
     * @returns Array of all ScreenshotItem instances across all executions
     */
    collectAllScreenshots(): ScreenshotItem[];
    /**
     * Serialize the dump to files with screenshots as separate PNG files.
     * Creates:
     * - {basePath} - dump JSON with { $screenshot: id } references
     * - {basePath}.screenshots/ - PNG files
     *
     * @param basePath - Base path for the dump file
     */
    serializeToFiles(basePath: string): void;
    /**
     * Read dump from files and return JSON string with inline screenshots.
     * Reads the dump JSON and screenshot files, then inlines the base64 data.
     *
     * @param basePath - Base path for the dump file
     * @returns JSON string with inline screenshots ({ base64: "..." } format)
     */
    static fromFilesAsInlineJson(basePath: string): string;
    /**
     * Clean up all files associated with a serialized dump.
     *
     * @param basePath - Base path for the dump file
     */
    static cleanupFiles(basePath: string): void;
    /**
     * Get all file paths associated with a serialized dump.
     *
     * @param basePath - Base path for the dump file
     * @returns Array of all associated file paths
     */
    static getFilePaths(basePath: string): string[];
}
export type GroupedActionDump = ReportActionDump;
export declare const GroupedActionDump: typeof ReportActionDump;
