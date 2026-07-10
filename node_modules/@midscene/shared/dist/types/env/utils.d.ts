import { GlobalConfigManager } from './global-config-manager';
import { ModelConfigManager } from './model-config-manager';
import { type GLOBAL_ENV_KEYS, type MODEL_ENV_KEYS } from './types';
export declare const globalModelConfigManager: ModelConfigManager;
export declare const globalConfigManager: GlobalConfigManager;
export declare const getPreferredLanguage: () => string;
export declare const overrideAIConfig: (newConfig: Partial<Record<(typeof GLOBAL_ENV_KEYS)[number] | (typeof MODEL_ENV_KEYS)[number], string>>, extendMode?: boolean) => void;
