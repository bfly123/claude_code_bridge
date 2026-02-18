import { z } from 'zod';
import { type ActionAPIContext, type ErrorInferenceObject, type MaybePromise } from '../utils.js';
import { type SafeResult } from './shared.js';
export * from './shared.js';
export type ActionAccept = 'form' | 'json';
export type ActionHandler<TInputSchema, TOutput> = TInputSchema extends z.ZodType ? (input: z.infer<TInputSchema>, context: ActionAPIContext) => MaybePromise<TOutput> : (input: any, context: ActionAPIContext) => MaybePromise<TOutput>;
export type ActionReturnType<T extends ActionHandler<any, any>> = Awaited<ReturnType<T>>;
export type ActionClient<TOutput, TAccept extends ActionAccept | undefined, TInputSchema extends z.ZodType | undefined> = TInputSchema extends z.ZodType ? ((input: TAccept extends 'form' ? FormData : z.input<TInputSchema>) => Promise<SafeResult<z.input<TInputSchema> extends ErrorInferenceObject ? z.input<TInputSchema> : ErrorInferenceObject, Awaited<TOutput>>>) & {
    queryString: string;
    orThrow: (input: TAccept extends 'form' ? FormData : z.input<TInputSchema>) => Promise<Awaited<TOutput>>;
} : ((input?: any) => Promise<SafeResult<never, Awaited<TOutput>>>) & {
    orThrow: (input?: any) => Promise<Awaited<TOutput>>;
};
export declare function defineAction<TOutput, TAccept extends ActionAccept | undefined = undefined, TInputSchema extends z.ZodType | undefined = TAccept extends 'form' ? z.ZodType<FormData> : undefined>({ accept, input: inputSchema, handler, }: {
    input?: TInputSchema;
    accept?: TAccept;
    handler: ActionHandler<TInputSchema, TOutput>;
}): ActionClient<TOutput, TAccept, TInputSchema> & string;
/** Transform form data to an object based on a Zod schema. */
export declare function formDataToObject<T extends z.AnyZodObject>(formData: FormData, schema: T): Record<string, unknown>;
