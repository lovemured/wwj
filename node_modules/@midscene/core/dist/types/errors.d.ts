import type { ServiceDump } from './types';
export declare class ServiceError extends Error {
    dump: ServiceDump;
    constructor(message: string, dump: ServiceDump);
}
