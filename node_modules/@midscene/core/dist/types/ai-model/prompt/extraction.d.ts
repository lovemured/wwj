import type { AIDataExtractionResponse, ServiceExtractParam } from '../../types';
export declare function buildTypeQueryDemandValue(type: 'Boolean' | 'Number' | 'String' | 'Assert' | 'WaitFor', demand: ServiceExtractParam): string;
/**
 * Parse XML response from LLM and convert to AIDataExtractionResponse
 */
export declare function parseXMLExtractionResponse<T>(xmlString: string): AIDataExtractionResponse<T>;
export declare function systemPromptToExtract(options?: {
    screenshotIncluded?: boolean;
    referenceImagesIncluded?: boolean;
}): string;
export declare const extractDataQueryPrompt: (pageDescription: string, dataQuery: string | Record<string, string>) => string;
