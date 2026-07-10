import { z } from 'zod';
import type { UserPromptLike } from './types';
export declare function composeUserPrompt(input: {
    prompt: string;
    image?: unknown;
    imageName?: unknown;
    convertHttpImage2Base64?: unknown;
}): UserPromptLike;
export declare const promptInputExtraSchema: {
    image: z.ZodOptional<z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodString, "many">]>>;
    imageName: z.ZodOptional<z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodString, "many">]>>;
    convertHttpImage2Base64: z.ZodOptional<z.ZodUnion<[z.ZodBoolean, z.ZodString]>>;
};
