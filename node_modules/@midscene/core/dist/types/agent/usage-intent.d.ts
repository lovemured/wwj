import type { AIUsageInfo } from '../types';
import type { TIntent } from '@midscene/shared/env';
export declare function withUsageIntent(usage: AIUsageInfo | undefined, intent: TIntent): AIUsageInfo | undefined;
