import type { ChatCompletionAssistantMessageParam } from 'openai/resources/chat/completions';
import { ChatCompletionChunk } from 'openai/resources';
import type { ChatCompletionMessage } from 'openai/resources/chat/completions';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ChatCompletionMessageToolCall } from 'openai/resources';
import type { ChatCompletionTool } from 'openai/resources/chat/completions';
import type { ChatCompletionToolChoiceOption } from 'openai/resources/chat/completions';
import type { ChatCompletionToolMessageParam } from 'openai/resources/chat/completions';
import type { ChatCompletionUserMessageParam } from 'openai/resources/chat/completions';
import { Client as Client_2 } from '@modelcontextprotocol/sdk/client/index.js';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { OpenAI } from 'openai/index.mjs';
import type { ReasoningEffort } from 'openai/resources';
import * as z from 'zod';

export declare type AbortEvent = z.infer<typeof AbortEventSchema>;

/**
 * Turn abort event - User aborted the current turn
 * Triggers completion of orphaned tool calls
 */
declare const AbortEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"abort">;
    data: z.ZodObject<{
        reason: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        reason: string;
    }, {
        reason: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "abort";
    data: {
        reason: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "abort";
    data: {
        reason: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

declare type AgentAction = (typeof AgentActions)[number];

declare const AgentActions: readonly ["fix", "fix-pr-comment", "task"];

declare type ApiKeyAuthInfo = {
    readonly type: "api-key";
    readonly apiKey: string;
    readonly host: string;
};

/**
 * An assessed command, with its identifier and whether it is read-only.
 */
declare type AssessedCommand = {
    /**
     * The command identifier, e.g. "rm" or "git push".
     */
    readonly identifier: string;
    /**
     * Whether the command is read-only (i.e. does not modify state).
     */
    readOnly: boolean;
};

export declare type AssistantIntentEvent = z.infer<typeof AssistantIntentEventSchema>;

declare const AssistantIntentEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"assistant.intent">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        intent: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        intent: string;
    }, {
        intent: string;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "assistant.intent";
    data: {
        intent: string;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "assistant.intent";
    data: {
        intent: string;
    };
    timestamp: string;
    parentId: string | null;
}>;

export declare type AssistantMessageEvent = z.infer<typeof AssistantMessageEventSchema>;

/**
 * An event that is emitted by the `Client` for each message it receives from the LLM.
 *
 * Currently does not include telemetry.
 */
declare type AssistantMessageEvent_2 = {
    kind: "message";
    turn?: number;
    callId?: string;
    modelCall?: ModelCallParam;
    message: ChatCompletionMessageParamsWithToolCalls & ReasoningMessageParam;
};

/**
 * Assistant text response (with optional tool requests)
 */
declare const AssistantMessageEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.message">;
    data: z.ZodObject<{
        messageId: z.ZodString;
        content: z.ZodString;
        chunkContent: z.ZodOptional<z.ZodString>;
        totalResponseSizeBytes: z.ZodOptional<z.ZodNumber>;
        toolRequests: z.ZodOptional<z.ZodArray<z.ZodObject<{
            toolCallId: z.ZodString;
            name: z.ZodString;
            arguments: z.ZodUnknown;
        }, "strip", z.ZodTypeAny, {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }, {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }>, "many">>;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    }, {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.message";
    data: {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.message";
    data: {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type AssistantTurnEndEvent = z.infer<typeof AssistantTurnEndEventSchema>;

/**
 * Agent completes a turn
 */
declare const AssistantTurnEndEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.turn_end">;
    data: z.ZodObject<{
        turnId: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        turnId: string;
    }, {
        turnId: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.turn_end";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.turn_end";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type AssistantTurnStartEvent = z.infer<typeof AssistantTurnStartEventSchema>;

/**
 * Agent starts processing a turn
 */
declare const AssistantTurnStartEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.turn_start">;
    data: z.ZodObject<{
        turnId: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        turnId: string;
    }, {
        turnId: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.turn_start";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.turn_start";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type AssistantUsageEvent = z.infer<typeof AssistantUsageEventSchema>;

/**
 * Assistant usage metrics (ephemeral event for UI updates)
 * Used to track model usage, tokens, costs, and durations without persisting to disk
 * Emitted in app.tsx's onModelCallSuccess callback
 */
declare const AssistantUsageEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"assistant.usage">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        model: z.ZodOptional<z.ZodString>;
        inputTokens: z.ZodOptional<z.ZodNumber>;
        outputTokens: z.ZodOptional<z.ZodNumber>;
        cacheReadTokens: z.ZodOptional<z.ZodNumber>;
        cacheWriteTokens: z.ZodOptional<z.ZodNumber>;
        cost: z.ZodOptional<z.ZodNumber>;
        duration: z.ZodOptional<z.ZodNumber>;
        initiator: z.ZodOptional<z.ZodString>;
        apiCallId: z.ZodOptional<z.ZodString>;
        providerCallId: z.ZodOptional<z.ZodString>;
        quotaSnapshots: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodObject<{
            isUnlimitedEntitlement: z.ZodBoolean;
            entitlementRequests: z.ZodNumber;
            usedRequests: z.ZodNumber;
            usageAllowedWithExhaustedQuota: z.ZodBoolean;
            overage: z.ZodNumber;
            overageAllowedWithExhaustedQuota: z.ZodBoolean;
            remainingPercentage: z.ZodNumber;
            resetDate: z.ZodOptional<z.ZodDate>;
        }, "strip", z.ZodTypeAny, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }>>>;
    }, "strip", z.ZodTypeAny, {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    }, {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "assistant.usage";
    data: {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "assistant.usage";
    data: {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    };
    timestamp: string;
    parentId: string | null;
}>;

export declare type Attachment = z.infer<typeof AttachmentSchema>;

declare const AttachmentSchema: z.ZodObject<{
    type: z.ZodEnum<["file", "directory"]>;
    path: z.ZodString;
    displayName: z.ZodString;
}, "strip", z.ZodTypeAny, {
    type: "file" | "directory";
    path: string;
    displayName: string;
}, {
    type: "file" | "directory";
    path: string;
    displayName: string;
}>;

/**
 * Represents the authentication information for a user.
 */
declare type AuthInfo = HMACAuthInfo | EnvAuthInfo | UserAuthInfo | GhCliAuthInfo | ApiKeyAuthInfo | TokenAuthInfo;

/**
 * Base interface for all hook inputs
 */
export declare interface BaseHookInput {
    timestamp: number;
    cwd: string;
}

export declare abstract class BaseLogger implements RunnerLogger {
    protected logLevel?: LogLevel;
    protected debugEnvironmentVariables?: string[];
    private secretFilter;
    constructor(logLevel?: LogLevel, debugEnvironmentVariables?: string[]);
    filterSecrets(messageOrError: string | Error): string | Error;
    /**
     * Returns true if the log level is not set, or the log level is set and the level is enabled.
     */
    shouldLog(level: LogLevel): boolean;
    isDebug(): boolean;
    abstract log(message: string): void;
    abstract info(message: string): void;
    abstract debug(message: string): void;
    abstract notice(message: string | Error): void;
    abstract warning(message: string | Error): void;
    abstract error(message: string | Error): void;
    abstract startGroup(name: string, level?: LogLevel): void;
    abstract endGroup(level?: LogLevel): void;
}

declare type BinaryResult = {
    data: string;
    mimeType: string;
    type: string;
    /**
     * A description of the binary data.
     */
    description?: string;
};

declare type ChatCompletionMessageParamsWithToolCalls = Omit<ChatCompletionAssistantMessageParam, "tool_calls"> & {
    tool_calls?: CopilotChatCompletionMessageToolCall[];
};

declare interface Client {
    readonly model: string;
    getCompletionWithTools(systemMessage: string, initialMessages: ChatCompletionMessageParam[], tools: Tool[], options?: GetCompletionWithToolsOptions): AsyncGenerator<Event_2>;
}

/**
 * The ideal set of options that a `{@link Client}` expose.
 */
declare type ClientOptions = {
    /**
     * The model to use for LLM completions.
     */
    model?: string;
    /**
     * The proportion of the model's input/prompt token limit
     * that should be given to tools as their token budget.
     */
    toolTokenBudgetProportion?: number;
    retryPolicy?: ClientRetryPolicy;
    /**
     * If for the current model, a higher level of thinking is possible, use it.
     * @default false
     */
    thinkingMode?: boolean;
    requestHeaders?: Record<string, string>;
    /**
     * If true, enables cache control checkpoints on messages sent to the model.
     * This allows downstream services to better manage caching of responses.
     * Defaults to false.
     */
    enableCacheControl?: boolean;
    /**
     * The default reasoning effort level for the model to use, if supported by the client.
     */
    defaultReasoningEffort?: ReasoningEffort;
};

/**
 * Retry policies for the AI client.
 */
declare type ClientRetryPolicy = {
    /**
     * The maximum number of retries for **any** type of retryable failure or error.
     */
    maxRetries?: number;
    /**
     * Specific error codes that should always be retried.
     * - If a `number`, that specific error code will be retried.
     * - If a `[number, number]`, all error codes in the range will be retried (inclusive).
     * - If a `[number, undefined]`, all error codes greater than or equal to the first number will be retried.
     * - To retry all error codes based on an upper bound, simply use `[0, number]`.
     *
     * Some error codes are retried by default even if not specified here, for example 429 (rate limit exceeded).
     */
    errorCodesToRetry?: (number | [number, number | undefined])[];
    /**
     * How to handle retries for rate limiting (429) errors. If a policy is not provided, a default
     * policy will be used.
     */
    rateLimitRetryPolicy?: {
        /**
         * The default wait time in between retries if the server does not
         * provide a `retry-after` header.
         */
        defaultRetryAfterSeconds?: number;
        /**
         * The initial extra wait time in between retries. The extra wait time will
         * be added to the `retry-after` header value (or {@link defaultRetryAfterSeconds} if
         * the header is not present). After each retry, the extra wait time will grow beyond
         * this value according to the {@link retryBackoffExtraGrowth} factor.
         */
        initialRetryBackoffExtraSeconds?: number;
        /**
         * The growth factor for the retry backoff extra time. E.g. 2x, 3x, etc.
         */
        retryBackoffExtraGrowth?: number;
        /**
         * The maximum wait time in between retries.
         */
        maxRetryAfterSeconds?: number;
    };
};

declare type Command = {
    readonly identifier: string;
    readonly readOnly: boolean;
};

declare type CompactionCompletedEvent = {
    kind: "compaction_completed";
    turn: number;
    performedBy: string;
    success: boolean;
    error?: string;
    compactionResult?: CompactionEventResult;
};

declare type CompactionEvent = CompactionStartedEvent | CompactionCompletedEvent;

declare type CompactionEventResult = {
    tokenLimit: number;
    preCompactionTokens: number;
    preCompactionMessagesLength: number;
    postCompactionTokens: number;
    postCompactionMessagesLength: number;
    tokensRemoved: number;
    messagesRemoved: number;
    summaryContent: string;
    compactionTokensUsed: {
        input: number;
        output: number;
        cachedInput: number;
    };
};

/**
 * Result of a conversation history compaction operation.
 */
export declare interface CompactionResult {
    success: boolean;
    tokensRemoved: number;
    messagesRemoved: number;
    summaryContent: string;
}

declare type CompactionStartedEvent = {
    kind: "compaction_started";
    turn: number;
    performedBy: string;
};

export declare function completeOrphanedToolCalls(messages: ChatCompletionMessageParam[], logger: RunnerLogger): ChatCompletionMessageParam[];

declare type CompletionWithToolsModel = {
    readonly name: string;
    readonly id?: string;
    readonly capabilities?: {
        readonly supports?: {
            readonly vision?: boolean;
        };
        readonly limits?: {
            readonly max_prompt_tokens?: number;
            readonly max_context_window_tokens?: number;
            readonly vision?: {
                readonly supported_media_types: string[];
                readonly max_prompt_images: number;
                readonly max_prompt_image_size: number;
            };
        };
    };
};

export declare class CompoundLogger implements RunnerLogger {
    readonly loggers: RunnerLogger[];
    constructor(loggers: RunnerLogger[]);
    isDebug(): boolean;
    debug(message: string): void;
    log(message: string): void;
    info(message: string): void;
    notice(message: string | Error): void;
    warning(message: string | Error): void;
    error(message: string | Error): void;
    startGroup(name: string, level?: LogLevel): void;
    endGroup(level?: LogLevel): void;
}

export declare class ConsoleLogger extends BaseLogger implements RunnerLogger {
    constructor(logLevel?: LogLevel, debugEnvironmentVariables?: string[]);
    log(message: string): void;
    debug(message: string): void;
    info(message: string): void;
    notice(message: string | Error): void;
    warning(message: string | Error): void;
    error(message: string | Error): void;
    startGroup(name: string, level?: LogLevel): void;
    endGroup(level?: LogLevel): void;
}

declare enum ContentFilterMode {
    None = "none",
    Markdown = "markdown",
    HiddenCharacters = "hidden_characters"
}

/**
 * Note: agent sessions API depend on this type!
 */
declare type CopilotChatCompletionChunk = Omit<ChatCompletionChunk, "choices"> & {
    choices: CopilotChatCompletionChunkChoices;
};

declare type CopilotChatCompletionChunkChoice = Omit<ChatCompletionChunk.Choice, "delta"> & {
    delta: CopilotChatCompletionChunkDelta;
};

declare type CopilotChatCompletionChunkChoices = Array<CopilotChatCompletionChunkChoice>;

declare type CopilotChatCompletionChunkDelta = Omit<ChatCompletionChunk.Choice.Delta, "tool_calls"> & ReasoningMessageParam & {
    tool_calls?: Array<CopilotChatCompletionToolCallDelta>;
};

/**
 * Re-export the OpenAI union type for convenience.
 * ChatCompletionMessageToolCall = ChatCompletionMessageFunctionToolCall | ChatCompletionMessageCustomToolCall
 */
declare type CopilotChatCompletionMessageToolCall = ChatCompletionMessageToolCall & {
    index?: number;
};

/**
 * Streaming tool call delta that supports both function and custom tool calls.
 */
declare type CopilotChatCompletionToolCallDelta = FunctionToolCallDelta | CustomToolCallDelta;

export declare type CustomAgentCompletedEvent = z.infer<typeof CustomAgentCompletedEventSchema>;

/**
 * Custom agent execution completes successfully
 */
declare const CustomAgentCompletedEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.completed">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        agentName: string;
    }, {
        toolCallId: string;
        agentName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.completed";
    data: {
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.completed";
    data: {
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type CustomAgentFailedEvent = z.infer<typeof CustomAgentFailedEventSchema>;

/**
 * Custom agent execution fails
 */
declare const CustomAgentFailedEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.failed">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
        error: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        error: string;
        toolCallId: string;
        agentName: string;
    }, {
        error: string;
        toolCallId: string;
        agentName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.failed";
    data: {
        error: string;
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.failed";
    data: {
        error: string;
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type CustomAgentSelectedEvent = z.infer<typeof CustomAgentSelectedEventSchema>;

/**
 * Custom agent selected for the session
 */
declare const CustomAgentSelectedEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.selected">;
    data: z.ZodObject<{
        agentName: z.ZodString;
        agentDisplayName: z.ZodString;
        tools: z.ZodNullable<z.ZodArray<z.ZodString, "many">>;
    }, "strip", z.ZodTypeAny, {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    }, {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.selected";
    data: {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.selected";
    data: {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type CustomAgentStartedEvent = z.infer<typeof CustomAgentStartedEventSchema>;

/**
 * Custom agent execution begins
 */
declare const CustomAgentStartedEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.started">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
        agentDisplayName: z.ZodString;
        agentDescription: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    }, {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.started";
    data: {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.started";
    data: {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * Type for a custom tool call delta (streaming).
 */
declare type CustomToolCallDelta = {
    index: number;
    id?: string;
    type?: "custom";
    custom?: {
        name?: string;
        input?: string;
    };
};

/**
 * Format specification for custom tools that use grammar-based input.
 */
declare type CustomToolInputFormat = {
    /**
     * The type of format. Currently only "grammar" is supported.
     */
    type: "grammar";
    /**
     * The syntax of the grammar (e.g., "lark").
     */
    syntax: string;
    /**
     * The grammar definition.
     */
    definition: string;
};

declare type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends (infer U)[] ? U[] : T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export declare const DEFAULT_INTEGRATION_ID = "copilot-developer-cli";

declare const defaultFeatureFlags: {
    CUSTOM_AGENTS: boolean;
    CCA_DELEGATE: boolean;
    COPILOT_KITTY: boolean;
    CONTINUITY: boolean;
    CONTINUITY_REMOTE_CONTROL: boolean;
    FEATURE_FLAG_TEST: boolean;
    S2STOKENS: boolean;
    COPILOT_SWE_AGENT_UNIFIED_TASK_TOOL: boolean;
    COPILOT_SWE_AGENT_BACKGROUND_AGENTS: boolean;
    COPILOT_SWE_AGENT_EXPANDED_BUILTIN_AGENTS: boolean;
};

/**
 * Enables a model's policy for the current user.
 * This is used for models that are available but require user consent (policy.state !== 'enabled').
 */
export declare function enableModelPolicy(authInfo: AuthInfo, modelId: string, integrationId?: string, sessionId?: string, logger?: RunnerLogger): Promise<EnableModelPolicyResult>;

export declare type EnableModelPolicyResult = {
    success: boolean;
    error?: string;
    canBeEnabled?: boolean;
};

/** Represents the Personal Access Token (PAT) or server-to-server token authentication information. */
declare type EnvAuthInfo = {
    readonly type: "env";
    readonly host: string;
    /** The login of the user. Undefined for server-to-server tokens (ghs_). */
    readonly login?: string;
    readonly token: string;
    readonly envVar: string;
};

/**
 * EnvValueMode controls how the value of a key/value pair in the `env` block of an MCP server config is
 * interpreted. `direct` means the value is used as-is. `indirect` means the value is the name
 * of an environment variable whose value should be used.
 */
declare type EnvValueMode = "direct" | "indirect";

export declare type ErrorOccurredHook = (input: ErrorOccurredHookInput) => Promise<ErrorOccurredHookOutput | void>;

/**
 * Error occurred hook types
 */
export declare interface ErrorOccurredHookInput extends BaseHookInput {
    error: Error;
    errorContext: "model_call" | "tool_execution" | "system" | "user_input";
    recoverable: boolean;
}

export declare interface ErrorOccurredHookOutput {
    suppressOutput?: boolean;
    errorHandling?: "retry" | "skip" | "abort";
    retryCount?: number;
    userNotification?: string;
}

declare type Event_2 = MessageEvent_2 | ResponseEvent | ModelCallFailureEvent | TurnEvent | TruncationEvent | CompactionEvent | ImageProcessingEvent | ImageRemovalEvent | ModelCallSuccessEvent | ToolExecutionEvent;

declare type EventData<T extends EventType> = EventPayload<T>["data"];

declare type EventHandler<T extends EventType> = (event: EventPayload<T>) => void;

declare type EventPayload<T extends EventType> = Extract<SessionEvent, {
    type: T;
}>;

/**
 * Telemetry can be emitted by the runtime via progress events. Telemetry is attached to progress events
 * on a `telemetry` property whose type is this.
 */
declare type EventTelemetry<EventT = string, TelemetryT extends Telemetry = Telemetry> = {
    /**
     * The name of the telemetry event associated with the emitted runtime progress event.
     */
    event: EventT;
    /**
     * String-esque properties that are associated with the telemetry event.
     * WARNING: Do not put sensitive data here. Use restrictedProperties for that.
     */
    properties: TelemetryT["properties"];
    /**
     * String-esque properties that are associated with the telemetry event. These are only available on the restricted topics
     */
    restrictedProperties: TelemetryT["restrictedProperties"];
    /**
     * Number-esque metrics that are associated with the telemetry event. Both integer and floating point values are possible.
     */
    metrics: TelemetryT["metrics"];
};

declare type EventType = SessionEvent["type"];

export declare function executeHooks<TInput extends BaseHookInput, TOutput>(hooks: ((input: TInput) => Promise<TOutput | void>)[] | undefined, input: TInput, logger: RunnerLogger): Promise<void | TOutput>;

export declare interface ExternalToolDefinition {
    name: string;
    description: string;
    parameters?: Record<string, unknown>;
}

export declare type ExternalToolDispatcher = (request: ExternalToolInvocation) => Promise<ToolResult>;

export declare interface ExternalToolInvocation {
    sessionId: string;
    toolCallId: string;
    toolName: string;
    arguments: unknown;
    abortSignal?: AbortSignal;
}

declare type FeatureFlags = Readonly<typeof defaultFeatureFlags>;

export declare class FileLogger extends BaseLogger implements RunnerLogger {
    private readonly filePath;
    /** Promise that resolves when pending writes are complete. Used to serialize
     * writes and for testing. */
    writeQueue: Promise<void>;
    constructor(filePath: string, logLevel?: LogLevel, debugEnvironmentVariables?: string[]);
    log(message: string): void;
    debug(message: string): void;
    info(message: string): void;
    notice(message: string | Error): void;
    warning(message: string | Error): void;
    error(message: string | Error): void;
    startGroup(name: string, level?: LogLevel): void;
    endGroup(level?: LogLevel): void;
    write(category: string, message: string): void;
    private performWrite;
}

/**
 * Type for a function tool call delta (streaming).
 */
declare type FunctionToolCallDelta = {
    index: number;
    id?: string;
    type?: "function";
    function?: {
        name?: string;
        arguments?: string;
    };
};

/**
 * Retrieves the list of available models based on policies and integration including capabilities and
 * billing information, which may be cached from previous calls.
 *
 * This list is in order of preference to be the default model for new sessions where the first model is
 * the most preferred.  It can be empty if all model policies are disabled.
 *
 * @deprecated Used solely by vscode-copilot-chat extension, use {@link retrieveAvailableModels} instead.
 */
export declare function getAvailableModels(authInfo: AuthInfo): Promise<Model[]>;

declare type GetCompletionWithToolsOptions = {
    /**
     * If `true`, then calls do `getCompletionWithTools` will check if the token counts of
     * the initial system messages, user messages, and tool definitions, exceed the limits
     * of the model. If they do, then the call will throw an error. If `false`, then the
     * call will not perform any checks.
     *
     * Defaults to `false`.
     */
    failIfInitialInputsTooLong?: boolean;
    toolChoice?: ChatCompletionToolChoiceOption;
    requestHeaders?: Record<string, string>;
    /**
     * If true, performs the request in streaming mode. This results in additional events
     * as each chunk is received from the service.
     */
    stream?: boolean;
    /**
     * If this call is a continuation of a previous `getCompletionWithTools` call, this specifies what turn
     * that conversation was/is on. This is used to determine the initial turn count in this
     * call to `getCompletionWithTools`.
     */
    initialTurnCount?: number;
    /**
     * If `true`, then the client will execute tools in parallel if model supports `parallel_tool_calls`.
     * If `false`, then the client will execute tools sequentially even if the model returns multiple tool calls.
     * Defaults to false.
     */
    executeToolsInParallel?: boolean;
    /**
     * Processors provide a way to do work during different stages of the completion with tools
     * lifecycle. Processors will be called in the order they are provided.
     */
    processors?: {
        preRequest?: IPreRequestProcessor[];
        onRequestError?: IOnRequestErrorProcessor[];
        preToolsExecution?: IPreToolsExecutionProcessor[];
        postToolExecution?: IPostToolExecutionProcessor[];
        onStreamingChunk?: IOnStreamingChunkProcessor[];
    };
    /**
     * Signal to abort the completion request.
     */
    abortSignal?: AbortSignal;
    /**
     * An optional identifier for the completion with tools call. This can be used for logging
     * and tracing purposes.
     */
    callId?: string;
    /**
     * The reasoning effort level for the model to use, if supported by the client.
     */
    reasoningEffort?: ReasoningEffort;
};

/** Gets the list of available custom agents. */
export declare function getCustomAgents(authInfo: AuthInfo, workingDir: string, integrationId?: string, logger?: RunnerLogger): Promise<SweCustomAgent[]>;

/** Represents the GitHub CLI authentication information. */
declare type GhCliAuthInfo = {
    readonly type: "gh-cli";
    readonly host: string;
    readonly login: string;
    readonly token: string;
};

declare interface HandoffProgress {
    step: HandoffStep;
    status: "in-progress" | "complete";
    message?: string;
}

declare type HandoffStep = "load-session" | "validate-repo" | "check-changes" | "checkout-branch" | "create-session" | "save-session";

/** Represents the HMAC-based authentication information. */
declare type HMACAuthInfo = {
    readonly type: "hmac";
    readonly hmac: string;
};

export declare type HookEndEvent = z.infer<typeof HookEndEventSchema>;

/**
 * Hook invocation completes
 */
declare const HookEndEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"hook.end">;
    data: z.ZodObject<{
        hookInvocationId: z.ZodString;
        hookType: z.ZodString;
        output: z.ZodUnknown;
        success: z.ZodBoolean;
        error: z.ZodOptional<z.ZodObject<{
            message: z.ZodString;
            stack: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            message: string;
            stack?: string | undefined;
        }, {
            message: string;
            stack?: string | undefined;
        }>>;
    }, "strip", z.ZodTypeAny, {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    }, {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "hook.end";
    data: {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "hook.end";
    data: {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type HookStartEvent = z.infer<typeof HookStartEventSchema>;

/**
 * Hook invocation begins
 */
declare const HookStartEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"hook.start">;
    data: z.ZodObject<{
        hookInvocationId: z.ZodString;
        hookType: z.ZodString;
        input: z.ZodUnknown;
    }, "strip", z.ZodTypeAny, {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    }, {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "hook.start";
    data: {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "hook.start";
    data: {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * This event is temporary until we extract vision support from being internal to getCompletionWithTools.
 */
declare type ImageProcessingEvent = {
    kind: "image_processing";
    turn: number;
    imageProcessingMetrics: ImageProcessingMetrics;
};

declare type ImageProcessingMetrics = ({
    imagesExtractedCount: number;
    base64ImagesCount: number;
    imagesRemovedDueToSize: number;
    imagesRemovedDueToDimensions: number;
    imagesResized: number;
    imagesResolvedFromGitHubMCPCount: number;
    allImagesSendToLlm?: number;
} & Record<string, number>) | Record<string, never>;

/**
 * This event is temporary until we extract vision support from being internal to getCompletionWithTools.
 */
declare type ImageRemovalEvent = {
    kind: "images_removed";
    turn: number;
    largeImagesRemoved?: number;
    imagesRemoved: number;
};

/**
 * A message to be injected into the conversation history after tool execution.
 * Used by tools like skills that need to add content to the conversation.
 */
declare type InjectedUserMessage = {
    /**
     * The content to inject as a user message.
     */
    content: string;
    /**
     * A source identifier for tracking where this message came from.
     * Used for filtering in the timeline display.
     * Example: "skill-pdf", "skill-code-reviewer"
     */
    source: string;
};

export declare const INTEGRATION_ID: string;

export declare namespace internal {
    export {
        HandoffStep,
        HandoffProgress,
        LocalSessionManager
    }
}

declare interface IOnRequestErrorProcessor extends IToJson {
    /**
     * Called before an error is rethrown by the client. The processor may modify
     * the error in place.
     */
    preErrorThrow(error: unknown): Promise<void>;
    /**
     * Called when a request to the model fails. The processor should not modify
     * the error.
     */
    onRequestError(context: OnRequestErrorContext): Promise<OnRequestErrorResult | void>;
}

declare interface IOnStreamingChunkProcessor extends IToJson {
    /**
     * Called when a streaming chunk is received.
     */
    onStreamingChunk(context: StreamingChunkContext): void;
}

declare interface IPostToolExecutionProcessor extends IToJson {
    /**
     * Called after a tool has been executed. The processor should not
     * modify the tool result.
     */
    postToolExecution(context: PostToolExecutionContext): Promise<void>;
}

declare interface IPreRequestProcessor extends IToJson {
    /**
     * Called before a request (including retries of requests) is made to the model.
     *
     * - Any {@link Event}s emitted by this method will be re-emitted by the completion with tools call.
     */
    preRequest(context: PreRequestContext): AsyncGenerator<Event_2>;
}

declare interface IPreToolsExecutionProcessor extends IToJson {
    /**
     * Called before any tool calls are executed.
     */
    preToolsExecution(context: PreToolsExecutionContext): Promise<PreToolsExecutionResult>;
}

/**
 * The complete settings type that represents all possible configuration options.
 */
declare interface IRuntimeSettings {
    version: string;
    clientName: string;
    github: {
        serverUrl: string;
        uploadsUrl: string;
        downloadsUrl: string;
        secretScanningUrl: string;
        host: string;
        hostProtocol: string;
        token: string;
        user: {
            name: string;
            email: string;
            actorId?: number;
            actorLogin?: string;
        };
        owner: {
            id: number;
            name: string;
        };
        repo: {
            id: number;
            name: string;
            branch: string;
            commit: string;
            readWrite: boolean;
        };
        pr: {
            commitCount?: number;
        };
    };
    problem: {
        statement: string;
        contentFilterMode?: ContentFilterMode;
        action: AgentAction;
        customAgentName?: string;
    };
    service: {
        instance: {
            id: string;
        };
        /**
         * - Options beyond `model` are currently only respected
         * when going through `RuntimeHarness` methods.
         * - The value of this {@link ClientOptions.model} is NOT
         * the name of a model, it is AgentName:ModelName.
         */
        agent: ClientOptions;
        /**
         * Settings for tools that are used by the agent. Refer to the
         * source/documentation for each tool for their specific settings.
         */
        tools: {
            [toolName: string]: {
                [key: string]: unknown;
            };
        };
        callback: {
            url: string;
        };
    };
    api: {
        aipSweAgent: {
            token: string;
        };
        anthropic: {
            key: string;
            baseUrl: string;
        };
        openai: {
            baseUrl: string;
            apiKey: string;
            azureKeyVaultUri: string;
            azureSecretName: string;
            azure: {
                url: string;
                apiVersion: string;
            };
        };
        copilot: {
            url: string;
            integrationId: string;
            hmacKey: string;
            azureKeyVaultUri: string;
            token: string;
            useSessions: boolean;
            useAsyncSessions: boolean;
            sessionId: string;
            previousSessionIds: string[];
        };
        github: {
            /**
             * The GITHUB_PERSONAL_ACCESS_TOKEN that is passed to `github-mcp-server` when it is
             * started. (Currently only supported in the `cpd` entry point.)
             */
            mcpServerToken: string;
        };
    };
    blackbird: {
        mode: "initial-search" | "tool";
        backfillScoreThreshold?: number;
        repoNwo?: string;
        /**
         * The auth object contains the credentials for Blackbird's Metis API.
         * - modelBasedRetrievalToken: Token for model-based retrieval.
         * - metisApiKey: API key for Metis.
         */
        auth: {
            modelBasedRetrievalToken: string;
            metisApiKey: string;
        };
    };
    swebench_base_commit?: string;
    trajectory: {
        outputFile: string;
    };
    logs: {
        eventsLogDir: string;
    };
    job: {
        nonce?: string;
        eventType?: string;
    };
    onlineEvaluation: {
        disableOnlineEvaluation?: boolean;
        enableOnlineEvaluationOutputFile?: boolean;
    };
    tools: {
        bash: {
            /**
             * The default timeout for bash commands in seconds. If undefined, a default of 120 seconds (2 minutes) is used.
             */
            defaultTimeout?: number;
        };
        /**
         * Settings shared by all validation tools.
         */
        validation?: {
            /**
             * The shared timeout budget for all the validation tools in seconds. If undefined, a default of 180 seconds is used.
             * This timeout is shared across all validation tools, and once the total time spent exceeds this budget, no further validation tools will be run.
             * A validation tool will be cancelled if it is in progress when the budget is exceeded.
             */
            timeout?: number;
        };
    };
    /**
     * The set of feature flags passed to the agent runtime process by sweagentd.
     *
     * Only flags listed in internal/launcher/runtime_feature_flags.go are passed
     * to the runtime.
     *
     * To add a new flag:
     * - Define it in accordance with the feature flag docs: https://thehub.github.com/epd/engineering/products-and-services/dotcom/features/feature-flags/
     * - Add it to runtime_feature_flags.go
     * - Check whether it exists in the following object.
     *
     * Read a feature flag value with: @see isFeatureFlagEnabled
     *
     *    if (isFeatureFlagEnabled(settings, 'copilot_swe_agent_flag_name')) {
     *    }
     *
     * Report feature flag values in telemetry with: @see featureFlagsAsString in
     * a property named @see FEATURE_FLAGS_TELEMETRY_PROPERTY_NAME.
     *
     * NOTE: feature flag names may be visible to the user in logs or other output.
     */
    featureFlags: {
        [key: string]: boolean;
    };
    /**
     * EXP experiment configuration
     */
    experiments: {
        [key: string]: string;
    };
    /**
     * How many ms the runtime/the thing hosting the runtime has available to run
     * before it is considered to have timed out.
     */
    timeoutMs: number;
    /**
     * The time when the runtime/the thing hosting the runtime started, in ms since epoch.
     * May not be 100% accurate. Not typically set by hand.
     */
    startTimeMs: number;
}

/**
 * Returns true if the DEBUG or COPILOT_AGENT_DEBUG environment variable is set to 1 or true (case-insensitive).
 * If additionalVariables are provided, they are also checked.
 * @param additionalVariables Additional environment variables to check for debug logging.
 */
export declare function isDebugEnvironment(...additionalVariables: string[]): boolean;

/**
 * Something which must have an implementation of `toJSON()`. This can be used
 * for classes whose instances will likely be used with `JSON.stringify()` to avoid
 * any issues with stringification such as circular references or non-enumerable properties.
 *
 * More information on `toJSON()`: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON/stringify#:~:text=If%20the%20value%20has%20a%20toJSON()%20method%2C%20it%27s%20responsible%20to%20define%20what%20data%20will%20be%20serialized.
 */
declare interface IToJson {
    toJSON(): string;
}

/**
 * Session class with event sourcing
 */
export declare class LocalSession extends Session<LocalSessionMetadata> {
    private callback;
    private isProcessing;
    private messageQueue;
    private immediatePromptProcessor;
    private abortController?;
    private activeCustomAgents;
    mcpHostCache: McpHostCache;
    private modelListCache;
    private warnedUnknownTools;
    /**
     * Creates a new Session instance.
     *
     * In practice, use SessionManager.createSession() to create sessions and SessionManager.getSession() / SessionManager.getLastSession() to retrieve existing sessions.
     *
     * @param options - Configuration options for the session including model provider, tools, hooks, environment settings, and metadata (sessionId, startTime, modifiedTime). If metadata is not provided, new values are generated.
     */
    constructor(options?: SessionOptions);
    /**
     * Updates session options after creation.
     * This method allows selectively updating configuration options without recreating the session.
     * Only the provided options will be updated; omitted options remain unchanged.
     *
     * @param options - Partial session options to update
     *
     * @example
     * ```typescript
     * // Update multiple options at once
     * session.updateOptions({
     *   logger: fileLogger,
     *   mcpServers: mcpConfig,
     *   customAgents: loadedAgents
     * });
     *
     * // Or use convenience methods for single updates
     * session.setAuthInfo(newAuthInfo); // Preferred for auth
     * session.setSelectedModel(newModel); // Preferred for model
     * ```
     */
    updateOptions(options: Partial<UpdatableSessionOptions>): void;
    getMetadata(): LocalSessionMetadata;
    /**
     * Sends a message to the session and executes the agentic loop.
     * Messages can be queued or sent immediately during an ongoing turn.
     *
     * @param options - Send options including prompt, attachments, and mode
     * @param options.prompt - The prompt text to send
     * @param options.attachments - Optional file/directory attachments
     * @param options.mode - "enqueue" (default) adds to queue and processes when ready, "immediate" injects during current turn
     * @param options.abortController - Optional AbortController to abort the send operation
     * @returns A Promise that resolves when the message has been queued or processed
     *
     * @example
     * ```typescript
     * // Send a message (default enqueue mode)
     * session.send({
     *   prompt: "What files are in this directory?",
     *   attachments: [{ type: "directory", path: "/path/to/dir" }]
     * });
     *
     * // Send immediate message during processing
     * session.send({
     *   prompt: "Continue with that approach",
     *   mode: "immediate"
     * });
     * ```
     */
    send(options: SendOptions): Promise<void>;
    abort(): Promise<void>;
    /**
     * Compacts the conversation history into a single summary message.
     * This method is used by the /compact slash command for manual compaction.
     * Uses the same system message and tools as the core agent loop for consistency.
     *
     * @returns Promise that resolves with compaction results
     * @throws Error if compaction fails or prerequisites aren't met
     */
    compactHistory(): Promise<CompactionResult>;
    /**
     * Initialize MCP host if configured
     */
    private initializeMcpHost;
    /**
     * Initializes the session and validates tool filter configuration.
     * This method should be called after the session is fully configured (auth, model, MCP servers)
     * but before the first message is sent. It eagerly builds and caches the tool definitions and system message
     * so they are available for features like /context that need them before the first message.
     * It will also emit warnings for any unknown tool names specified in availableTools or excludedTools.
     *
     * @returns Promise that resolves when initialization and validation is complete
     */
    initializeAndValidateTools(): Promise<void>;
    /**
     * Shared method to build settings and initialize tools.
     * Used by both initializeAndValidateTools() and runAgenticLoop().
     *
     * @param problemStatement - Optional problem statement for settings (used by runAgenticLoop)
     * @returns Settings and tools, or undefined if initialization failed
     */
    private buildSettingsAndTools;
    private isToolEnabled;
    /**
     * Validates tool filter configuration and emits info about disabled tools and warnings for unknown tool names.
     */
    private validateToolFilters;
    /**
     * Builds custom agent tools from the available custom agents.
     *
     * @param customAgents - Array of custom agents to convert to tools
     * @param parentTools - Tools available to the custom agents
     * @param runtimeContext - Runtime context for custom agent execution
     * @param mcpServerProvider - Optional MCP server provider for custom agent MCP servers
     * @returns Promise that resolves to an array of custom agent tools
     */
    private buildCustomAgentTools;
    /**
     * Filters tools based on the selected custom agent, if any.
     *
     * @param allTools - All available tools
     * @returns Filtered tools based on selected custom agent restrictions
     */
    private filterToolsForSelectedAgent;
    private invokeCallbacks;
    private getModelList;
    /**
     * Creates a client instance with current session configuration.
     * Extracted from runAgenticLoop to allow reuse for standalone LLM calls.
     *
     * @returns Promise that resolves to a configured client and settings
     * @throws Error if session was not created with authentication info or custom provider
     */
    private getClient;
    /**
     * Generates a summarized version of the conversation context suitable for delegation.
     * Uses an LLM to create a concise summary of the existing conversation that fits
     * within size constraints (20k characters).
     *
     * @returns Promise that resolves to a markdown summary of the session context
     * @throws Error if session was not created with authentication info or if summarization fails
     */
    getContextSummary(): Promise<string>;
    /**
     * Executes the full agentic loop for a given prompt.
     * This method orchestrates the complete AI agent workflow including:
     * - Running hooks (userPromptSubmitted, sessionStart, preToolUse, postToolUse, sessionEnd)
     * - Building and sending the prompt to the language model
     * - Processing model responses and tool calls
     * - Executing tools and feeding results back to the model
     * - Emitting events throughout the process
     *
     * This is the core method that powers the `send()` functionality.
     * Most users should call `send()` instead, which handles queuing and mode selection.
     *
     * @param prompt - The user's prompt/instruction text
     * @param attachments - Optional array of file or directory attachments to include with the prompt
     * @returns A Promise that resolves when the agent loop completes
     * @throws Error if the session was not created with authentication info/custom provider or model
     */
    private runAgenticLoop;
}

/**
 * SessionManager subclass that persists sessions to JSONL files.
 * Uses SessionEventState for all file system operations.
 */
declare class LocalSessionManager implements SessionManager<LocalSessionMetadata, LocalSession> {
    private sessionWriters;
    private copilotVersion;
    private flushDebounceMs;
    private logger;
    constructor({ version, flushDebounceMs, ...options }: LocalSessionManagerOptions);
    /**
     * Create a new file-backed session
     */
    createSession(options?: SessionOptions, emitStart?: boolean): Promise<LocalSession>;
    private loadHooks;
    /**
     * Get existing session by ID
     * ALWAYS loads from disk to ensure freshness
     * Supports both JSONL and legacy JSON formats
     *
     * @throws Error if the session exists but cannot be parsed (e.g., unknown event types, corrupt data)
     * @returns The session, or undefined if the session does not exist
     */
    getSession(options: SessionOptions & {
        sessionId: string;
    }, resume?: boolean): Promise<LocalSession | undefined>;
    /**
     * Get the most recently updated session
     */
    getLastSession(options?: Omit<SessionOptions, "sessionId">): Promise<LocalSession | undefined>;
    /**
     * Get the ID of the most recently updated session
     */
    getLastSessionId(): Promise<string | undefined>;
    saveSession(session: Session): Promise<void>;
    private loadSession;
    /**
     * Load a legacy JSON session and convert it to LocalSession
     * This creates a session.import_legacy event to preserve the legacy data
     */
    private loadLegacySession;
    /**
     * List all sessions by reading from disk
     */
    listSessions(): Promise<LocalSessionMetadata[]>;
    /**
     * Delete a session from disk
     */
    deleteSession(sessionId: string): Promise<void>;
    /**
     * Close session - flushes pending data and cleans up resources but keeps session in memory
     */
    closeSession(sessionId: string): Promise<void>;
    /**
     * Get the sessions directory path (for debugging/logging)
     */
    getSessionsDirectory(): string;
    setLogger(logger: RunnerLogger): void;
    /**
     * Handoff a remote session to local by validating repository, checking git state,
     * and creating a local session with the remote session's events.
     * This is an async generator that yields progress updates.
     *
     * @param remoteSession - The remote session to handoff
     * @param sessionOptions - Optional session options to pass to createSession
     * @yields HandoffProgress updates for each step
     * @returns A new local session with the same events
     * @throws Error if validation fails or git operations fail
     */
    handoffSession(remoteSession: Session, sessionOptions?: SessionOptions): AsyncGenerator<HandoffProgress, LocalSession, undefined>;
    /**
     * Helper method to fetch from git remote
     */
    private gitFetch;
}

declare type LocalSessionManagerOptions = {
    version?: string;
    flushDebounceMs?: number;
} & SessionManagerOptions;

export declare interface LocalSessionMetadata extends SessionMetadata {
    readonly isRemote: false;
}

export declare enum LogLevel {
    None = 0,
    Error = 1,
    Warning = 2,
    Info = 3,
    Debug = 4,
    All = 4,// Logs everything
    Default = 3
}

/**
 * Manages the lifecycle of MCP (Model Context Protocol) servers and provides access to their tools.
 */
declare class McpHost {
    protected logger: RunnerLogger;
    private registry;
    private processor;
    private config;
    private startServersPromise?;
    private transport;
    private disabledServers;
    constructor(logger: RunnerLogger, mcpConfig: string | MCPServersConfig, disabledServers?: string[], envValueMode?: EnvValueMode);
    /**
     * Called when a server sends a tools/list_changed notification
     */
    private handleToolsChanged;
    startServers(): Promise<void>;
    /**
     * Extension point for subclasses to inject default servers into the config.
     * This method is called during startServers() before processing the servers.
     * Subclasses should override this method and mutate the config parameter in place
     * to add custom server configurations.
     */
    protected injectDefaultServers(_config: MCPServersConfig): Promise<void>;
    private processServersWithExtensions;
    stopServers(): Promise<void>;
    /**
     * Gets all available tools from the MCP servers. Starts the servers with @see startServers if they have not already been started.
     * the tools returned should not be used after @see stopServers has been called.
     *
     * @param settings - The runtime settings.
     * @param logger - The logger instance.
     * @param permissions - Permissions configuration for tool access.
     * @returns A promise that resolves to an array of tools.
     */
    getTools(settings: RuntimeSettings, logger: RunnerLogger, permissions: PermissionsConfig): Promise<Tool[]>;
    /**
     * Gets the current MCP configuration.
     */
    getConfig(): MCPServersConfig;
    /**
     * Gets all connected MCP clients.
     * @returns A record of server names to their client instances
     */
    getClients(): Record<string, Client_2>;
    /**
     * Start a single MCP server with the given configuration
     * @param serverName - Unique name for the server
     * @param config - Server configuration
     * @returns Promise that resolves when server is started
     */
    startServer(serverName: string, config: MCPServerConfig): Promise<void>;
    /**
     * Stop a single MCP server
     * @param serverName - Name of the server to stop
     * @returns Promise that resolves when server is stopped
     */
    stopServer(serverName: string): Promise<void>;
    /**
     * Restart a server with new configuration
     * @param serverName - Name of the server to restart
     * @param config - New server configuration
     * @returns Promise that resolves when server is restarted
     */
    restartServer(serverName: string, config: MCPServerConfig): Promise<void>;
    /**
     * Check if a server is currently running
     * @param serverName - Name of the server to check
     * @returns True if server is running
     */
    isServerRunning(serverName: string): boolean;
    /**
     * Check if a server is disabled
     * @param serverName - Name of the server to check
     * @returns True if server is disabled
     */
    isServerDisabled(serverName: string): boolean;
    /**
     * Disable a server at runtime (does not persist across sessions)
     * @param serverName - Name of the server to disable
     * @returns Promise that resolves when server is disabled
     */
    disableServer(serverName: string): Promise<void>;
    /**
     * Enable a previously disabled server at runtime
     * @param serverName - Name of the server to enable
     * @returns Promise that resolves when server is enabled
     */
    enableServer(serverName: string): Promise<void>;
    /**
     * Extension point for subclasses to start a built in server that is not listed in
     * the MCP Config.
     * @param serverName - Name of the server to enable
     * @returns Promise that resolves when server handling is complete
     */
    protected startBuiltInServer(_serverName: string): Promise<void>;
    /**
     * Get the configuration for a running server
     * @param serverName - Name of the server
     * @returns Server configuration or undefined if not found
     */
    getServerConfig(serverName: string): MCPServerConfig | undefined;
}

/**
 * Cache that maintains a mapping of agent ID to MCP host.
 * The root agent uses an empty string as its ID.
 */
declare class McpHostCache {
    private hosts;
    private logger;
    constructor(logger: RunnerLogger);
    /**
     * Get or create an MCP host for the given agent ID.
     * Returns undefined if mcpServers is empty or undefined.
     */
    getOrCreateHost(agentId: string, mcpServers: Record<string, MCPServerConfig> | undefined): Promise<McpHost | undefined>;
    /**
     * Get an existing host for the given agent ID.
     */
    getHost(agentId: string): McpHost | undefined;
    /**
     * Stop and remove all MCP hosts.
     */
    cleanup(): Promise<void>;
    /**
     * Get the number of hosts in the cache.
     */
    size(): number;
}

declare interface MCPInMemoryServerConfig extends MCPServerConfigBase {
    type: "memory";
    serverInstance: McpServer;
}

declare interface MCPLocalServerConfig extends MCPServerConfigBase {
    type?: "local" | "stdio";
    command: string;
    args: string[];
    /**
     * An object of the environment variables to pass to the server.
     *
     * The interpretation of this object depends on the environment variable mode:
     * - In 'indirect' mode (default): Hybrid approach for backward compatibility
     *   - If value contains $ or ${...}, tries variable substitution first
     *   - If substitution succeeds (changes the value), uses the resolved value
     *   - Otherwise, treats value as the name of an env var to read from current process
     *   Example: { "FOO": "BAR" } sets FOO=process.env.BAR (legacy)
     *   Example: { "FOO": "$BAR" } sets FOO=process.env.BAR (variable expansion)
     *   Example: { "FOO": "${BAR:-default}" } sets FOO=process.env.BAR or "default"
     * - In 'direct' mode: Key is the env var name to set in the MCP server,
     *   Value is the literal value to set. Supports variable expansion:
     *   - $VAR or ${VAR}: expands to process.env.VAR
     *   - ${VAR:-default}: expands to process.env.VAR, or "default" if VAR is undefined
     *   Example: { "FOO": "bar" } sets FOO=bar
     *   Example: { "FOO": "${BAR}" } or { "FOO": "$BAR" } sets FOO=process.env.BAR
     *   Example: { "FOO": "${BAR:-fallback}" } sets FOO=process.env.BAR or "fallback"
     *   Example: { "URL": "https://${HOST}:${PORT}" } expands both variables
     *
     * Empty means no env vars passed.
     */
    env?: Record<string, string>;
    cwd?: string;
}

/**
 * A permission request for invoking an MCP tool.
 */
declare type MCPPermissionRequest = {
    readonly kind: "mcp";
    /** The name of the MCP Server being targeted e.g. "github-mcp-server" */
    readonly serverName: string;
    /** The name of the tool being targeted e.g. "list_issues" */
    readonly toolName: string;
    /** The title of the tool being targeted e.g. "List Issues" */
    readonly toolTitle: string;
    /**
     * The _hopefully_ JSON arguments that will be passed to the MCP tool.
     *
     * This should be an object, but it's not parsed before this point so we can't guarantee that.
     * */
    readonly args: unknown;
    /**
     * Whether the tool is read-only (e.g. a `view` operation) or not (e.g. an `edit` operation).
     */
    readonly readOnly: boolean;
};

declare interface MCPRemoteServerConfig extends MCPServerConfigBase {
    type: "http" | "sse";
    /**
     * URL of the remote server
     * NOTE: this has to be converted to a URL object before giving to transport.
     * TransportFactory will handle this conversion.
     */
    url: string;
    /**
     * Optional. HTTP headers to include in requests to the remote server.
     * This can be used for authentication or other purposes.
     * For example, you might include an Authorization header.
     */
    headers?: Record<string, string>;
}

declare type MCPServerConfig = MCPLocalServerConfig | MCPRemoteServerConfig | MCPInMemoryServerConfig;

declare interface MCPServerConfigBase {
    /**
     * List of tools to include from this server. [] means none. "*" means all.
     */
    tools: string[];
    /**
     * Indicates "remote" or "local" server type.
     * If not specified, defaults to "local".
     */
    type?: string;
    /**
     * Optional. Denotes if this is a MCP server we have defined to be used when
     * the user has not provided their own MCP server config.
     *
     * Marked optional as configs coming from users will/should not have this set. Defaults to `false`.
     */
    isDefaultServer?: boolean;
    /**
     * Optional. Either a content filter mode for all tools from this server, or a map of tool name to content filter mode for the tool with that name.
     * If not specified, defaults to "hidden_characters"
     */
    filterMapping?: Record<string, ContentFilterMode> | ContentFilterMode;
    /**
     * Optional. Timeout in milliseconds for tool calls to this server.
     * If not specified, a default is used.
     */
    timeout?: number;
}

declare interface MCPServersConfig {
    mcpServers: Record<string, MCPServerConfig>;
}

/**
 * All types of message events that can be emitted by the `Client`.
 */
declare type MessageEvent_2 = {
    kind: "message";
    turn?: number;
    callId?: string;
    modelCall?: ModelCallParam;
    message: ChatCompletionMessageParam & ReasoningMessageParam;
} | AssistantMessageEvent_2 | UserMessageEvent_2 | ToolMessageEvent;

declare type Model = {
    id: string;
    name: string;
    capabilities: {
        supports: {
            vision: boolean;
        };
        limits: {
            max_prompt_tokens?: number;
            max_context_window_tokens: number;
            vision?: {
                supported_media_types: string[];
                max_prompt_images: number;
                max_prompt_image_size: number;
            };
        };
    };
    policy?: {
        state: "enabled" | "disabled" | "unconfigured";
        terms: string;
    };
    billing?: {
        multiplier: number;
    };
};

declare type ModelCallFailureEvent = {
    kind: "model_call_failure";
    turn: number;
    callId?: string;
    modelCallDurationMs: number;
    /**
     * The model call that failed, if available.
     */
    modelCall: ModelCallParam;
    /**
     * A string representation of the messages sent as input to the model call, if available.
     */
    requestMessages?: string;
};

/**
 * -----------------------------------------------------------------------
 * Events
 * -----------------------------------------------------------------------
 *
 * Event (Union Type)
 * ├── TurnStartedEvent
 * ├── TurnEndedEvent
 * ├── TurnFailedEvent
 * ├── TurnRetryEvent
 * ├── ModelCallSuccessEvent
 * ├── ModelCallFailureEvent
 * ├── ToolExecutionEvent
 * ├── ImageProcessingEvent
 * ├── ImageRemovalEvent
 * ├── TruncationEvent
 * ├── MessageEvent
 * │   ├── AssistantMessageEvent
 * │   ├── UserMessageEvent
 * │   └── ToolMessageEvent
 * ├── ResponseEvent
 * └── SessionLogEvent
 */
/**
 * All types of events that can be emitted by the `Client`.
 */
declare interface ModelCallParam {
    api_id?: string;
    model?: string;
    error?: string;
    status?: number;
    request_id?: string;
    initiator?: string;
}

declare type ModelCallSuccessEvent = {
    kind: "model_call_success";
    turn: number;
    callId?: string;
    modelCallDurationMs: number;
    /**
     * Time to first token in milliseconds. Only available for streaming requests.
     */
    ttftMs?: number;
    /**
     * Average inter-token latency in milliseconds. Only available for streaming requests.
     * Calculated as the average time between successive tokens.
     */
    interTokenLatencyMs?: number;
    modelCall: ModelCallParam;
    responseChunk: CopilotChatCompletionChunk;
    responseUsage: OpenAI.ChatCompletion["usage"];
    /**
     * A string representation of the messages sent as input to the model call, if available.
     */
    requestMessages?: string;
    quotaSnapshots?: Record<string, QuotaSnapshot>;
};

export declare class NoopLogger extends BaseLogger implements RunnerLogger {
    constructor();
    debug(_message: string): void;
    log(_message: string): void;
    info(_message: string): void;
    notice(_message: string | Error): void;
    warning(_message: string | Error): void;
    error(_message: string | Error): void;
    startGroup(_name: string, _level?: LogLevel): void;
    endGroup(_level?: LogLevel): void;
}

declare type OnRequestErrorContext = {
    /**
     * The current turn.
     */
    readonly turn: number;
    /**
     * The current retry attempt.
     */
    readonly retry: number;
    /**
     * The maximum number of retry attempts.
     */
    readonly maxRetries: number;
    /**
     * The error received in response to a request.
     */
    readonly error: unknown;
    /**
     * Information about the model being called.
     */
    readonly modelInfo: CompletionWithToolsModel;
    /**
     * The current {@link GetCompletionWithToolsOptions}
     */
    readonly getCompletionWithToolsOptions: GetCompletionWithToolsOptions | undefined;
};

declare type OnRequestErrorResult = {
    /**
     * If the processor does something to handle the error and wishes for there to be a retry
     * it should set this to how many milliseconds to wait before retrying.
     */
    retryAfter: number;
};

/**
 * A permission request which will be used to check tool or path usage against config and/or request user approval.
 */
declare type PermissionRequest = {
    toolCallId?: string;
} & (ShellPermissionRequest | WritePermissionRequest | MCPPermissionRequest | ReadPermissionRequest | UrlPermissionRequest);

/**
 * The result of requesting permissions.
 */
declare type PermissionRequestResult = {
    readonly kind: "approved";
} | {
    readonly kind: "denied-by-rules";
    rules: ReadonlyArray<Rule>;
} | {
    readonly kind: "denied-no-approval-rule-and-could-not-request-from-user";
} | {
    readonly kind: "denied-interactively-by-user";
};

/**
 * Configuration for permissions handling.
 *
 * For CCA, permissions requests are not required.
 */
declare type PermissionsConfig = {
    requestRequired: false;
} | {
    requestRequired: true;
    request: RequestPermissionFn;
};

/**
 * This is just a type to warn that there's a good chance it's not a real path, because
 * it was _very_ heuristically parsed out of a command.
 */
declare type PossiblePath = string;

/**
 * A possible URL that was heuristically parsed from a command.
 */
declare type PossibleUrl = {
    readonly url: string;
};

declare type PostToolExecutionContext = {
    /**
     * The current turn.
     */
    readonly turn: number;
    /**
     * What tool call was executed.
     */
    readonly toolCall: CopilotChatCompletionMessageToolCall;
    /**
     * The result of the tool call. Can be modified in place by the processor.
     */
    readonly toolResult: ToolResultExpanded;
    /**
     * Information about the model being called.
     */
    readonly modelInfo: CompletionWithToolsModel;
};

export declare type PostToolUseHook = (input: PostToolUseHookInput) => Promise<PostToolUseHookOutput | void>;

/**
 * Post-tool use hook types
 */
export declare interface PostToolUseHookInput extends BaseHookInput {
    toolName: string;
    toolArgs: unknown;
    toolResult: ToolResultExpanded;
}

export declare interface PostToolUseHookOutput {
    modifiedResult?: ToolResultExpanded;
    additionalContext?: string;
    suppressOutput?: boolean;
}

declare type PreRequestContext = {
    /**
     * An optional identifier for the completion with tools call. This can be used for logging
     * and tracing purposes.
     */
    readonly callId?: string;
    /**
     * The current turn.
     */
    readonly turn: number;
    /**
     * The current retry attempt.
     */
    readonly retry: number;
    /**
     * The messages that will be sent to the model for the request.
     * If modifying them, do so in place.
     */
    readonly messages: ChatCompletionMessageParam[];
    /**
     * The tool definitions that will be sent to the model for the request.
     * These should not be modified.
     */
    readonly toolDefinitions: ChatCompletionTool[];
    /**
     * Information about the model being called.
     */
    readonly modelInfo: CompletionWithToolsModel;
    /**
     * Additional headers to send with the request. If adding additional headers
     * then simply add to this object.
     */
    readonly additionalRequestHeaders: Record<string, string>;
    /**
     * The current {@link GetCompletionWithToolsOptions}
     */
    readonly getCompletionWithToolsOptions: GetCompletionWithToolsOptions | undefined;
    /**
     * The client that can be used to make additional LLM calls (e.g., for compaction).
     */
    readonly client: Client;
    /**
     * The rich tool objects with callbacks, needed for nested LLM calls.
     */
    readonly tools: Tool[];
};

declare type PreToolsExecutionContext = {
    /**
     * The current turn.
     */
    readonly turn: number;
    /**
     * What tool calls are being executed.
     */
    readonly toolCalls: CopilotChatCompletionMessageToolCall[];
    /**
     * Information about the model being called.
     */
    readonly modelInfo: CompletionWithToolsModel;
};

/**
 * Pre-tools execution procesors can either return nothing, or results for one or more
 * of the tools to be executed. These results will be given to the model in lieu of
 * performing the tool call and obtaining a result from the tool itself.
 */
declare type PreToolsExecutionResult = void | Map<string, ToolResultExpanded>;

export declare type PreToolUseHook = (input: PreToolUseHookInput) => Promise<PreToolUseHookOutput | void>;

/**
 * Pre-tool use hook types
 */
export declare interface PreToolUseHookInput extends BaseHookInput {
    toolName: string;
    toolArgs: unknown;
}

export declare interface PreToolUseHookOutput {
    permissionDecision?: "allow" | "deny" | "ask";
    permissionDecisionReason?: string;
    modifiedArgs?: unknown;
    additionalContext?: string;
    suppressOutput?: boolean;
}

/**
 * Configuration for a custom API provider (BYOK - Bring Your Own Key).
 * When set, bypasses Copilot API authentication and uses this provider instead.
 */
export declare interface ProviderConfig {
    /** Provider type. Defaults to "openai" for generic OpenAI-compatible APIs. */
    type?: "openai" | "azure" | "anthropic";
    /** Wire API format (openai/azure only). Defaults to "completions". */
    wireApi?: "completions" | "responses";
    /** API endpoint URL */
    baseUrl: string;
    /** API key. Optional for local providers like Ollama. */
    apiKey?: string;
    /** Azure-specific options */
    azure?: {
        /** API version. Defaults to "2024-10-21". */
        apiVersion?: string;
    };
}

/**
 * Functional query API that provides a Claude Code-inspired interface.
 * This is a thin wrapper around the Session class for simple use cases.
 *
 * @param options - Query configuration options
 * @returns AsyncGenerator of SessionEvent objects
 */
export declare function query(options: QueryOptions): AsyncIterable<SessionEvent>;

/**
 * Hook system with arrays of specific hook callbacks
 */
export declare interface QueryHooks {
    preToolUse?: PreToolUseHook[];
    postToolUse?: PostToolUseHook[];
    userPromptSubmitted?: UserPromptSubmittedHook[];
    sessionStart?: SessionStartHook[];
    sessionEnd?: SessionEndHook[];
    errorOccurred?: ErrorOccurredHook[];
}

export declare type QueryOptions = SessionOptions & {
    prompt: string;
    abortController?: AbortController;
};

declare type QuotaSnapshot = {
    /**
     * Whether or not it's an unlimited entitlement.
     */
    isUnlimitedEntitlement: boolean;
    /**
     * The number of requests included in the entitlement, or "-1" for unlimited
     * entitlement, so that the user/client can understand how much they get each
     * month/period; the value is an integer
     */
    entitlementRequests: number;
    /**
     * The count of requests used so far in this month/period, so that the
     * user/client can understand how much of their entitlement they have used;
     * the value is an integer
     */
    usedRequests: number;
    /**
     * Indicates whether usage is allowed once quota is exhausted, so that the
     * user/client can understand if they can continue usage at a pay-per-request
     * rate when entitlement is exhausted; the value is boolean
     */
    usageAllowedWithExhaustedQuota: boolean;
    /**
     * The count of overage requests made so far in this month/period, so that
     * the user/client can understand how much they have spent in pay-per-request
     * charges so far this month/period; the value is a decimal
     */
    overage: number;
    /**
     * Indicates whether overage is allowed once quota is exhausted, so that the
     * user/client can understand if they can continue usage at a pay-per-request
     * rate when entitlement is exhausted; the value is boolean
     */
    overageAllowedWithExhaustedQuota: boolean;
    /**
     * The percentage of the entitlement remaining at the snapshot timestamp, so
     * that the user/client can understand how much they have remaining and their
     * rate of usage; the value is a decimal
     */
    remainingPercentage: number;
    /**
     * The date when the quota resets, so that the user/client can know when they
     * next receive their entitlement; the value is an RFC3339 formatted UTC date;
     * if the entitlement is unlimited, this value is not included in the snapshot
     */
    resetDate?: Date;
};

/**
 * A permission request for reading file or directory contents.
 */
declare type ReadPermissionRequest = {
    readonly kind: "read";
    /** The intention of the edit operation, e.g. "Read file" or "List directory" */
    readonly intention: string;
    /** The path of the file or directory being read */
    readonly path: string;
};

declare type ReasoningMessageParam = {
    /**
     * An ID or encrypted value that allows the model to restore
     */
    reasoning_opaque?: string;
    /**
     * Human-readable text describing the model's thinking process.
     */
    reasoning_text?: string;
    /**
     * An encrypted representation of the model's internal state
     */
    encrypted_content?: string | undefined | null;
};

export declare class RemoteSession extends Session<RemoteSessionMetadata> {
    readonly repository: {
        name: string;
        owner: string;
        branch: string;
    };
    readonly remoteSessionIds: string[];
    readonly pullRequestNumber?: number;
    constructor(options: SessionOptions & {
        repository: {
            name: string;
            owner: string;
            branch: string;
        };
        remoteSessionIds: string[];
        pullRequestNumber?: number;
    });
    send(options: SendOptions): Promise<void>;
    abort(): Promise<void>;
    compactHistory(): Promise<CompactionResult>;
    getMetadata(): RemoteSessionMetadata;
}

export declare interface RemoteSessionMetadata extends SessionMetadata {
    readonly repository: {
        owner: string;
        name: string;
        branch: string;
    };
    readonly remoteSessionIds: string[];
    readonly pullRequestNumber?: number;
    readonly isRemote: true;
}

declare type RequestPermissionFn = (permission: PermissionRequest) => Promise<PermissionRequestResult>;

/**
 * An event that is emitted by the `Client` which contains the final response from the LLM.
 */
declare type ResponseEvent = {
    kind: "response";
    turn?: number;
    callId?: string;
    modelCall?: ModelCallParam;
    response: ChatCompletionMessage;
};

/**
 * Retrieves the list of available models based on policies and integration including capabilities and
 * billing information, which may be cached from previous calls.
 *
 * This list is in order of preference to be the default model for new sessions where the first model is
 * the most preferred.  It can be empty if all model policies are disabled.
 */
export declare function retrieveAvailableModels(authInfo: AuthInfo, copilotUrl: string | undefined, integrationId: string, sessionId: string, logger: RunnerLogger): Promise<Model[]>;

/**
 * A Rule defines a pattern for matching permission requests.
 *
 * It is unfortunately generically named because it is intended to match across
 * different types of tool uses, e.g. `Shell(touch)` or `GitHubMCP(list_issues)`,
 * `view(.env-secrets)`
 */
declare type Rule = {
    /**
     * The kind of rule that should be matched e.g. `Shell` or `GitHubMCP`.
     */
    readonly kind: string;
    /**
     * If null, matches all arguments to the kind.
     */
    readonly argument: string | null;
};

export declare interface RunnerLogger {
    /**
     * Log a message ignoring the configured log level.
     * This is useful for logging messages that should always be logged, regardless of the log level.
     * @param message The message to log.
     */
    log(message: string): void;
    /**
     * Returns true if the environment is set to debug.
     * Note: This is not the same as the log level being set to debug.
     */
    isDebug(): boolean;
    /**
     * Log a debug message. This is only logged if the log level is set to debug.
     * @param message The message to log.
     */
    debug(message: string): void;
    /**
     * Log an info message. This is only logged if the log level is set to info or debug.
     * @param message The message to log.
     */
    info(message: string): void;
    /**
     * Log a notice message. This is only logged if the log level is set to warning, info, or debug,
     * but logs using the logger's info method.
     * This is useful for logging messages that are not errors, but are important enough to log on
     * less verbose log levels.
     * @param message The message to log.
     */
    notice(message: string | Error): void;
    /**
     * Log a warning message. This is only logged if the log level is set to warning, info, or debug
     * @param message The message to log.
     */
    warning(message: string | Error): void;
    /**
     * Log an error message. This is only logged if the log level is set to error, warning, info, or debug
     * @param message The message to log.
     */
    error(message: string | Error): void;
    /**
     * Log a message that starts a new group.
     * @param name The name of the group.
     * @param level The log level of the group. Defaults to info.
     */
    startGroup(name: string, level?: LogLevel): void;
    /**
     * Log a message that ends the current group.
     * @param level The log level of the group. Defaults to info.
     */
    endGroup(level?: LogLevel): void;
}

declare type RuntimeSettings = DeepPartial<IRuntimeSettings>;

/**
 * Indicates the safety level of the assessed script.
 *
 * There may some cases where a script cannot be assessed (e.g. unparseable),
 * in which case we bail with a failure.
 */
declare type SafetyAssessment = {
    readonly result: "failed";
    /**
     * A human-readable reason why the safety assessment could not be completed.
     */
    readonly reason: string;
} | {
    readonly result: "completed";
    readonly commands: ReadonlyArray<AssessedCommand>;
    /**
     * Possible absolute file paths that the script might operate on, based on heuristic parsing.
     */
    readonly possiblePaths: ReadonlyArray<PossiblePath>;
    /**
     * Possible URLs that the script might access, based on heuristic parsing.
     */
    readonly possibleUrls: ReadonlyArray<PossibleUrl>;
    /**
     * Indicates whether any command in the script has redirection to write to a file.
     */
    readonly hasWriteFileRedirection: boolean;
    /**
     * Indicates whether a command can be approved for the rest of the running session.
     *
     * Simple commands like `git status` or `npm test` can be session approved
     * because their impact is predictable. Complex commands with substitutions,
     * variables, or side effects require per-invocation approval.
     *
     * Examples of session-approvable: `ls`, `git log`, `command1 && command2`
     * Examples requiring per-invocation: `rm -rf $DIR`, `find -exec`
     */
    readonly canOfferSessionApproval: boolean;
};

export declare interface SendOptions {
    prompt: string;
    attachments?: Attachment[];
    mode?: "enqueue" | "immediate";
    abortController?: AbortController;
}

export declare abstract class Session<SM extends SessionMetadata = SessionMetadata> {
    readonly sessionId: string;
    readonly startTime: Date;
    readonly modifiedTime: Date;
    readonly summary?: string;
    protected logger: RunnerLogger;
    private events;
    protected _chatMessages: ChatCompletionMessageParam[];
    protected _selectedModel: string | undefined;
    private eventProcessingQueue;
    private eventHandlers;
    private wildcardEventHandlers;
    protected integrationId: string;
    protected availableTools?: string[];
    protected excludedTools?: string[];
    protected executeToolsInParallel?: boolean;
    protected shellConfig?: ShellConfig;
    protected requestPermission?: (permissionRequest: PermissionRequest) => Promise<PermissionRequestResult>;
    protected mcpServers?: Record<string, MCPServerConfig>;
    protected mcpHost?: McpHost;
    protected hooks?: QueryHooks;
    protected customAgents?: SweCustomAgent[];
    protected selectedCustomAgent?: SweCustomAgent;
    protected organizationCustomInstructions?: string;
    protected skipCustomInstructions: boolean;
    protected systemMessageConfig?: SystemMessageConfig;
    protected workingDir: string;
    protected featureFlags?: FeatureFlags;
    protected skillDirectories?: string[];
    protected disabledSkills?: Set<string>;
    protected trajectoryFile?: string;
    protected eventsLogDirectory?: string;
    protected authInfo?: AuthInfo;
    protected copilotUrl?: string;
    protected provider?: ProviderConfig;
    protected onToolsUpdate?: (tools: Tool[]) => void;
    protected enableStreaming: boolean;
    protected handoffContext?: string;
    protected externalToolDefinitions?: ExternalToolDefinition[];
    protected externalToolDispatcher?: ExternalToolDispatcher;
    protected clientName?: string;
    protected currentSystemMessage?: string;
    protected currentToolMetadata?: ToolMetadata[];
    protected currentTools?: Tool[];
    abstract send(options: SendOptions): Promise<void>;
    abstract abort(): Promise<void>;
    /**
     * Initializes tools and validates tool filter configuration.
     * This method should be called after the session is fully configured (auth, model, MCP servers)
     * but before the first message is sent. It will emit warnings for any unknown tool names
     * specified in availableTools or excludedTools.
     *
     * Default implementation is a no-op. Override in subclasses that support tool validation.
     *
     * @returns Promise that resolves when initialization and validation is complete
     */
    initializeAndValidateTools(): Promise<void>;
    constructor(options?: SessionOptions);
    abstract getMetadata(): SM;
    static fromEvents<S extends Session, O extends SessionOptions = SessionOptions>(this: new (_options: O) => S, events: SessionEvent[], options?: O): Promise<S>;
    /**
     * Updates the authentication information for this session.
     * This is a convenience method equivalent to updateOptions({ authInfo }).
     *
     * @param authInfo - The new authentication information to use for this session
     */
    setAuthInfo(authInfo: AuthInfo | undefined): void;
    /**
     * Updates session options after creation.
     * This method allows selectively updating configuration options without recreating the session.
     * Only the provided options will be updated; omitted options remain unchanged.
     *
     * @param options - Partial session options to update
     *
     * @example
     * ```typescript
     * // Update multiple options at once
     * session.updateOptions({
     *   logger: fileLogger,
     *   mcpServers: mcpConfig,
     *   customAgents: loadedAgents
     * });
     *
     * // Or use convenience methods for single updates
     * session.setAuthInfo(newAuthInfo); // Preferred for auth
     * session.setSelectedModel(newModel); // Preferred for model
     * ```
     */
    updateOptions(options: Partial<UpdatableSessionOptions>): void;
    /**
     * Set a callback to be notified when tools are initialized/updated.
     * This is called during the agentic loop after tools are built and available.
     * Useful for UI components that need to display tool information.
     *
     * @param callback - Function to call with the available tools
     *
     * @example
     * ```typescript
     * session.setOnToolsUpdate((tools) => {
     *   console.log(`${tools.length} tools available`);
     *   updateToolsList(tools);
     * });
     * ```
     */
    setOnToolsUpdate(callback: (tools: Tool[]) => void): void;
    /**
     * Get list of available custom agents.
     * Returns the custom agents that were provided when the session was created.
     *
     * @returns Array of available custom agents
     */
    getAvailableCustomAgents(): SweCustomAgent[];
    /**
     * Select a custom agent for subsequent queries.
     * When a custom agent is selected, only that agent's tools (and required tools) will be available.
     * The selected custom agent will also be available as a tool to the main agent.
     *
     * @param agentId - The name/id of the custom agent to select
     * @throws Error if the agent is not found
     */
    selectCustomAgent(agentId: string): Promise<void>;
    /**
     * Clear custom agent selection.
     * After calling this, all tools will be available again and all custom agents
     * will be available as tools.
     */
    clearCustomAgent(): void;
    /**
     * Registers an event handler for specific event types or all events.
     * Supports both synchronous and asynchronous handlers.
     *
     * @param eventType - The event type to listen for (e.g., "assistant.message", "tool.execution_complete") or "*" for all events
     * @param handler - The handler function to call when the event is emitted. Can be sync or async.
     * @returns A function that unsubscribes the handler when called
     */
    on<K extends EventType>(eventType: K, handler: EventHandler<K>): () => void;
    on(eventType: "*", handler: WildcardEventHandler): () => void;
    /**
     * Emits an event to all registered handlers.
     * Automatically generates event fields (id, timestamp, parentId) and adds the event to the session history.
     * Triggers both legacy callbacks and new-style event handlers.
     *
     * @param eventType - The type of event to emit
     * @param data - The event data payload
     * @param ephemeral - Whether this event should be persisted (default: false)
     */
    private emitInternal;
    /**
     * Emits an event to all registered handlers.
     * Automatically generates event fields (id, timestamp, parentId) and adds the event to the session history.
     * Triggers both legacy callbacks and new-style event handlers. Does not allow emitting ephemeral events.
     *
     * @param eventType - The type of event to emit
     * @param data - The event data payload
     */
    emit<K extends EventType>(eventType: EventPayload<K>["ephemeral"] extends true ? never : K, data: EventData<K>): void;
    /**
     * Emits an ephemeral event (not persisted to disk).
     * Convenience method that calls emit() with ephemeral = true.
     *
     * @param eventType - The type of event to emit
     * @param data - The event data payload
     */
    emitEphemeral<K extends EventType>(eventType: EventPayload<K>["ephemeral"] extends false ? never : K, data: EventData<K>): void;
    /**
     * Returns all events that have occurred in the session.
     * Events are returned in chronological order and include all session lifecycle, user messages,
     * assistant responses, tool executions, and other session events.
     *
     * @returns A readonly array of all session events
     */
    getEvents(): readonly SessionEvent[];
    /**
     * Returns all chat messages reconstructed from session events.
     * Messages are processed asynchronously in order to handle attachments and ensure consistency.
     * Includes user messages, assistant messages, tool messages, and system messages.
     *
     * @returns A Promise that resolves to a readonly array of chat completion messages
     * ```
     */
    getChatMessages(): Promise<readonly ChatCompletionMessageParam[]>;
    /**
     * Returns chat messages that are part of the conversation context (excludes system messages).
     * Useful for displaying the user/assistant conversation without system prompts.
     *
     * @returns A Promise that resolves to an array of user, assistant, and tool messages
     */
    getChatContextMessages(): Promise<ChatCompletionMessageParam[]>;
    /**
     * Returns only system and developer messages from the chat history.
     * Useful for inspecting the system prompts and instructions given to the model.
     *
     * @returns A Promise that resolves to an array of system/developer messages
     */
    getSystemContextMessages(): Promise<ChatCompletionMessageParam[]>;
    /**
     * Returns the current system message used in the most recent agent turn.
     * This is the full system prompt that was sent to the model.
     *
     * @returns The system message string, or undefined if not yet initialized
     */
    getCurrentSystemMessage(): string | undefined;
    /**
     * Returns lightweight tool metadata for token counting.
     * Used by /context command to calculate token usage.
     *
     * @returns The array of tool metadata, or undefined if not yet initialized
     */
    getCurrentToolMetadata(): ToolMetadata[] | undefined;
    /**
     * Returns the currently selected model for this session.
     * The model may change during a session if `setSelectedModel` is called.
     *
     * @returns A Promise that resolves to the model identifier string, or undefined if no model is set
     */
    getSelectedModel(): Promise<string | undefined>;
    /**
     * Returns the organization custom instructions configured for this session.
     * These are additional instructions provided by the organization.
     *
     * @returns The organization custom instructions string, or undefined if not set
     */
    getOrganizationCustomInstructions(): string | undefined;
    /**
     * Returns whether custom instructions should be skipped for this session.
     *
     * @returns True if custom instructions should be skipped, false otherwise
     */
    getSkipCustomInstructions(): boolean;
    /**
     * Returns the system message configuration for this session.
     * This can be used to replace or append to the default system message.
     *
     * @returns The system message config, or undefined if not set
     */
    getSystemMessageConfig(): SystemMessageConfig | undefined;
    /**
     * Sets the selected model for this session and emits a model change event.
     * This allows switching models mid-session, with the change tracked in the event history.
     *
     * @param model - The model identifier to switch to
     * @returns A Promise that resolves when the model change event has been emitted
     */
    setSelectedModel(model: string): Promise<void>;
    /**
     * Compacts the conversation history into a single summary message.
     * Used by the /compact slash command for manual compaction.
     *
     * @returns Promise that resolves with compaction results
     * @throws Error if compaction fails or is not supported
     */
    abstract compactHistory(): Promise<CompactionResult>;
    /**
     * Get the ID of the last event (for parentId chaining)
     */
    private getLastEventId;
    /**
     * Add a function to the event processing queue to ensure sequential processing
     * Returns a promise that resolves when the function has been processed
     * Ensures that state updates from events are processed in order
     */
    private enqueueEventProcessing;
    /**
     * Process event to update internal state (_chatMessages, _selectedModel, etc.)
     */
    private processEventForState;
    private loadCustomAgents;
}

export declare type SessionCompactionCompleteData = SessionCompactionCompleteEvent["data"];

export declare type SessionCompactionCompleteEvent = z.infer<typeof SessionCompactionCompleteEventSchema>;

/**
 * Session compaction complete event - conversation history compaction finished (success or failure)
 */
declare const SessionCompactionCompleteEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.compaction_complete">;
    data: z.ZodObject<{
        success: z.ZodBoolean;
        error: z.ZodOptional<z.ZodString>;
        preCompactionTokens: z.ZodOptional<z.ZodNumber>;
        postCompactionTokens: z.ZodOptional<z.ZodNumber>;
        messagesRemoved: z.ZodOptional<z.ZodNumber>;
        tokensRemoved: z.ZodOptional<z.ZodNumber>;
        summaryContent: z.ZodOptional<z.ZodString>;
        compactionTokensUsed: z.ZodOptional<z.ZodObject<{
            input: z.ZodNumber;
            output: z.ZodNumber;
            cachedInput: z.ZodNumber;
        }, "strip", z.ZodTypeAny, {
            input: number;
            output: number;
            cachedInput: number;
        }, {
            input: number;
            output: number;
            cachedInput: number;
        }>>;
    }, "strip", z.ZodTypeAny, {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    }, {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.compaction_complete";
    data: {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.compaction_complete";
    data: {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionCompactionStartEvent = z.infer<typeof SessionCompactionStartEventSchema>;

/**
 * Session compaction started event - conversation history compaction has begun
 */
declare const SessionCompactionStartEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.compaction_start">;
    data: z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.compaction_start";
    data: {};
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.compaction_start";
    data: {};
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionEndHook = (input: SessionEndHookInput) => Promise<SessionEndHookOutput | void>;

/**
 * Session end hook types
 */
export declare interface SessionEndHookInput extends BaseHookInput {
    reason: "complete" | "error" | "abort" | "timeout" | "user_exit";
    finalMessage?: string;
    error?: Error;
}

export declare interface SessionEndHookOutput {
    suppressOutput?: boolean;
    cleanupActions?: string[];
    sessionSummary?: string;
}

export declare type SessionErrorEvent = z.infer<typeof SessionErrorEventSchema>;

/**
 * Error notification (for timeline/UI display)
 */
declare const SessionErrorEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.error">;
    data: z.ZodObject<{
        errorType: z.ZodString;
        message: z.ZodString;
        stack: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        message: string;
        errorType: string;
        stack?: string | undefined;
    }, {
        message: string;
        errorType: string;
        stack?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.error";
    data: {
        message: string;
        errorType: string;
        stack?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.error";
    data: {
        message: string;
        errorType: string;
        stack?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * Union of all session event types
 */
export declare type SessionEvent = z.infer<typeof SessionEventSchema>;

/**
 * Discriminated union of all event schemas
 */
export declare const SessionEventSchema: z.ZodDiscriminatedUnion<"type", [z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.start">;
    data: z.ZodObject<{
        sessionId: z.ZodString;
        version: z.ZodNumber;
        producer: z.ZodString;
        copilotVersion: z.ZodString;
        startTime: z.ZodString;
        selectedModel: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    }, {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.start";
    data: {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.start";
    data: {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.resume">;
    data: z.ZodObject<{
        resumeTime: z.ZodString;
        eventCount: z.ZodNumber;
    }, "strip", z.ZodTypeAny, {
        resumeTime: string;
        eventCount: number;
    }, {
        resumeTime: string;
        eventCount: number;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.resume";
    data: {
        resumeTime: string;
        eventCount: number;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.resume";
    data: {
        resumeTime: string;
        eventCount: number;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.error">;
    data: z.ZodObject<{
        errorType: z.ZodString;
        message: z.ZodString;
        stack: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        message: string;
        errorType: string;
        stack?: string | undefined;
    }, {
        message: string;
        errorType: string;
        stack?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.error";
    data: {
        message: string;
        errorType: string;
        stack?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.error";
    data: {
        message: string;
        errorType: string;
        stack?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"session.idle">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "session.idle";
    data: {};
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "session.idle";
    data: {};
    timestamp: string;
    parentId: string | null;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.info">;
    data: z.ZodObject<{
        infoType: z.ZodString;
        message: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        message: string;
        infoType: string;
    }, {
        message: string;
        infoType: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.info";
    data: {
        message: string;
        infoType: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.info";
    data: {
        message: string;
        infoType: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.model_change">;
    data: z.ZodObject<{
        previousModel: z.ZodOptional<z.ZodString>;
        newModel: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        newModel: string;
        previousModel?: string | undefined;
    }, {
        newModel: string;
        previousModel?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.model_change";
    data: {
        newModel: string;
        previousModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.model_change";
    data: {
        newModel: string;
        previousModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.import_legacy">;
    data: z.ZodObject<{
        legacySession: z.ZodObject<{
            sessionId: z.ZodString;
            startTime: z.ZodDate;
            chatMessages: z.ZodArray<z.ZodUnion<[z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"developer">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"system">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"image_url">;
                    image_url: z.ZodObject<{
                        url: z.ZodString;
                        detail: z.ZodOptional<z.ZodEnum<["auto", "low", "high"]>>;
                    }, "strip", z.ZodTypeAny, {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    }, {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                }, {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"input_audio">;
                    input_audio: z.ZodObject<{
                        data: z.ZodString;
                        format: z.ZodUnion<[z.ZodLiteral<"wav">, z.ZodLiteral<"mp3">]>;
                    }, "strip", z.ZodTypeAny, {
                        data: string;
                        format: "wav" | "mp3";
                    }, {
                        data: string;
                        format: "wav" | "mp3";
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                }, {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"file">;
                    file: z.ZodObject<{
                        file_date: z.ZodOptional<z.ZodString>;
                        file_id: z.ZodOptional<z.ZodString>;
                        filename: z.ZodOptional<z.ZodString>;
                    }, "strip", z.ZodTypeAny, {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    }, {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                }, {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                }>]>, "many">]>;
                role: z.ZodLiteral<"user">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            }, {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodOptional<z.ZodNullable<z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"refusal">;
                    refusal: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    refusal: string;
                    type: "refusal";
                }, {
                    refusal: string;
                    type: "refusal";
                }>]>, "many">]>>>;
                role: z.ZodLiteral<"assistant">;
                name: z.ZodOptional<z.ZodString>;
                refusal: z.ZodOptional<z.ZodNullable<z.ZodString>>;
                audio: z.ZodOptional<z.ZodNullable<z.ZodObject<{
                    id: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    id: string;
                }, {
                    id: string;
                }>>>;
                function_call: z.ZodOptional<z.ZodNullable<z.ZodObject<{
                    name: z.ZodString;
                    arguments: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    name: string;
                    arguments: string;
                }, {
                    name: string;
                    arguments: string;
                }>>>;
                tool_calls: z.ZodOptional<z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    id: z.ZodString;
                    type: z.ZodLiteral<"function">;
                    function: z.ZodObject<{
                        name: z.ZodString;
                        arguments: z.ZodString;
                    }, "strip", z.ZodTypeAny, {
                        name: string;
                        arguments: string;
                    }, {
                        name: string;
                        arguments: string;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                }, {
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                }>, z.ZodObject<{
                    id: z.ZodString;
                    type: z.ZodLiteral<"custom">;
                    custom: z.ZodObject<{
                        name: z.ZodString;
                        input: z.ZodString;
                    }, "strip", z.ZodTypeAny, {
                        name: string;
                        input: string;
                    }, {
                        name: string;
                        input: string;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                }, {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                }>]>, "many">>;
            }, "strip", z.ZodTypeAny, {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            }, {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"tool">;
                tool_call_id: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            }>, z.ZodObject<{
                content: z.ZodNullable<z.ZodString>;
                role: z.ZodLiteral<"function">;
                name: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                content: string | null;
                role: "function";
                name: string;
            }, {
                content: string | null;
                role: "function";
                name: string;
            }>]>, "many">;
            timeline: z.ZodArray<z.ZodIntersection<z.ZodUnion<[z.ZodObject<{
                type: z.ZodLiteral<"copilot">;
                text: z.ZodString;
                isStreaming: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            }, {
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"error">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "error";
                text: string;
            }, {
                type: "error";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"info">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "info";
                text: string;
            }, {
                type: "info";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"user">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "user";
                text: string;
            }, {
                type: "user";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"tool_call_requested">;
                callId: z.ZodString;
                name: z.ZodString;
                toolTitle: z.ZodOptional<z.ZodString>;
                intentionSummary: z.ZodNullable<z.ZodString>;
                arguments: z.ZodUnion<[z.ZodUnion<[z.ZodObject<{
                    command: z.ZodString;
                    description: z.ZodString;
                    timeout: z.ZodOptional<z.ZodNumber>;
                    sessionId: z.ZodOptional<z.ZodString>;
                    async: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    input: z.ZodString;
                    delay: z.ZodOptional<z.ZodNumber>;
                }, "strip", z.ZodTypeAny, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    delay: z.ZodNumber;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                    delay: number;
                }, {
                    sessionId: string;
                    delay: number;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                }, {
                    sessionId: string;
                }>]>, z.ZodDiscriminatedUnion<"command", [z.ZodObject<{
                    command: z.ZodLiteral<"view">;
                    path: z.ZodString;
                    view_range: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>>;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"create">;
                    path: z.ZodString;
                    file_text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "create";
                    file_text: string;
                }, {
                    path: string;
                    command: "create";
                    file_text: string;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"str_replace">;
                    path: z.ZodString;
                    new_str: z.ZodOptional<z.ZodString>;
                    old_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"insert">;
                    path: z.ZodString;
                    insert_line: z.ZodNumber;
                    new_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }>]>, z.ZodUnknown]>;
                partialOutput: z.ZodOptional<z.ZodString>;
                isHidden: z.ZodOptional<z.ZodBoolean>;
                isAlwaysExpanded: z.ZodOptional<z.ZodBoolean>;
                showNoContent: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }, {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"tool_call_completed">;
                callId: z.ZodString;
                name: z.ZodString;
                toolTitle: z.ZodOptional<z.ZodString>;
                intentionSummary: z.ZodNullable<z.ZodString>;
                result: z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"success">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"failure">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"rejected">;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "rejected";
                    markdown?: boolean | undefined;
                }, {
                    type: "rejected";
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"denied">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                }>]>;
                arguments: z.ZodUnion<[z.ZodUnion<[z.ZodObject<{
                    command: z.ZodString;
                    description: z.ZodString;
                    timeout: z.ZodOptional<z.ZodNumber>;
                    sessionId: z.ZodOptional<z.ZodString>;
                    async: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    input: z.ZodString;
                    delay: z.ZodOptional<z.ZodNumber>;
                }, "strip", z.ZodTypeAny, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    delay: z.ZodNumber;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                    delay: number;
                }, {
                    sessionId: string;
                    delay: number;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                }, {
                    sessionId: string;
                }>]>, z.ZodDiscriminatedUnion<"command", [z.ZodObject<{
                    command: z.ZodLiteral<"view">;
                    path: z.ZodString;
                    view_range: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>>;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"create">;
                    path: z.ZodString;
                    file_text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "create";
                    file_text: string;
                }, {
                    path: string;
                    command: "create";
                    file_text: string;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"str_replace">;
                    path: z.ZodString;
                    new_str: z.ZodOptional<z.ZodString>;
                    old_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"insert">;
                    path: z.ZodString;
                    insert_line: z.ZodNumber;
                    new_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }>]>, z.ZodUnknown]>;
                isHidden: z.ZodOptional<z.ZodBoolean>;
                isAlwaysExpanded: z.ZodOptional<z.ZodBoolean>;
                showNoContent: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }, {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }>]>, z.ZodObject<{
                id: z.ZodString;
                timestamp: z.ZodDate;
            }, "strip", z.ZodTypeAny, {
                id: string;
                timestamp: Date;
            }, {
                id: string;
                timestamp: Date;
            }>>, "many">;
            selectedModel: z.ZodOptional<z.ZodEnum<["claude-sonnet-4.5", "claude-haiku-4.5", "claude-opus-4.5", "claude-sonnet-4", "gpt-5.1-codex-max", "gpt-5.1-codex", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5.1-codex-mini", "gpt-5-mini", "gpt-4.1", "gemini-3-pro-preview"]>>;
        }, "strip", z.ZodTypeAny, {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        }, {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        }>;
        importTime: z.ZodString;
        sourceFile: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    }, {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.import_legacy";
    data: {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.import_legacy";
    data: {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.handoff">;
    data: z.ZodObject<{
        handoffTime: z.ZodString;
        sourceType: z.ZodEnum<["remote", "local"]>;
        repository: z.ZodOptional<z.ZodObject<{
            owner: z.ZodString;
            name: z.ZodString;
            branch: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            name: string;
            owner: string;
            branch?: string | undefined;
        }, {
            name: string;
            owner: string;
            branch?: string | undefined;
        }>>;
        context: z.ZodOptional<z.ZodString>;
        summary: z.ZodOptional<z.ZodString>;
        remoteSessionId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    }, {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.handoff";
    data: {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.handoff";
    data: {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.truncation">;
    data: z.ZodObject<{
        tokenLimit: z.ZodNumber;
        preTruncationTokensInMessages: z.ZodNumber;
        preTruncationMessagesLength: z.ZodNumber;
        postTruncationTokensInMessages: z.ZodNumber;
        postTruncationMessagesLength: z.ZodNumber;
        tokensRemovedDuringTruncation: z.ZodNumber;
        messagesRemovedDuringTruncation: z.ZodNumber;
        performedBy: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    }, {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.truncation";
    data: {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.truncation";
    data: {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.compaction_start">;
    data: z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.compaction_start";
    data: {};
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.compaction_start";
    data: {};
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.compaction_complete">;
    data: z.ZodObject<{
        success: z.ZodBoolean;
        error: z.ZodOptional<z.ZodString>;
        preCompactionTokens: z.ZodOptional<z.ZodNumber>;
        postCompactionTokens: z.ZodOptional<z.ZodNumber>;
        messagesRemoved: z.ZodOptional<z.ZodNumber>;
        tokensRemoved: z.ZodOptional<z.ZodNumber>;
        summaryContent: z.ZodOptional<z.ZodString>;
        compactionTokensUsed: z.ZodOptional<z.ZodObject<{
            input: z.ZodNumber;
            output: z.ZodNumber;
            cachedInput: z.ZodNumber;
        }, "strip", z.ZodTypeAny, {
            input: number;
            output: number;
            cachedInput: number;
        }, {
            input: number;
            output: number;
            cachedInput: number;
        }>>;
    }, "strip", z.ZodTypeAny, {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    }, {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.compaction_complete";
    data: {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.compaction_complete";
    data: {
        success: boolean;
        error?: string | undefined;
        preCompactionTokens?: number | undefined;
        postCompactionTokens?: number | undefined;
        messagesRemoved?: number | undefined;
        tokensRemoved?: number | undefined;
        summaryContent?: string | undefined;
        compactionTokensUsed?: {
            input: number;
            output: number;
            cachedInput: number;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"user.message">;
    data: z.ZodObject<{
        content: z.ZodString;
        transformedContent: z.ZodOptional<z.ZodString>;
        attachments: z.ZodOptional<z.ZodArray<z.ZodObject<{
            type: z.ZodEnum<["file", "directory"]>;
            path: z.ZodString;
            displayName: z.ZodString;
        }, "strip", z.ZodTypeAny, {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }, {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }>, "many">>;
        source: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    }, {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "user.message";
    data: {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "user.message";
    data: {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.turn_start">;
    data: z.ZodObject<{
        turnId: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        turnId: string;
    }, {
        turnId: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.turn_start";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.turn_start";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"assistant.intent">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        intent: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        intent: string;
    }, {
        intent: string;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "assistant.intent";
    data: {
        intent: string;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "assistant.intent";
    data: {
        intent: string;
    };
    timestamp: string;
    parentId: string | null;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.message">;
    data: z.ZodObject<{
        messageId: z.ZodString;
        content: z.ZodString;
        chunkContent: z.ZodOptional<z.ZodString>;
        totalResponseSizeBytes: z.ZodOptional<z.ZodNumber>;
        toolRequests: z.ZodOptional<z.ZodArray<z.ZodObject<{
            toolCallId: z.ZodString;
            name: z.ZodString;
            arguments: z.ZodUnknown;
        }, "strip", z.ZodTypeAny, {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }, {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }>, "many">>;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    }, {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.message";
    data: {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.message";
    data: {
        content: string;
        messageId: string;
        chunkContent?: string | undefined;
        totalResponseSizeBytes?: number | undefined;
        toolRequests?: {
            name: string;
            toolCallId: string;
            arguments?: unknown;
        }[] | undefined;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"assistant.turn_end">;
    data: z.ZodObject<{
        turnId: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        turnId: string;
    }, {
        turnId: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "assistant.turn_end";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "assistant.turn_end";
    data: {
        turnId: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"assistant.usage">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        model: z.ZodOptional<z.ZodString>;
        inputTokens: z.ZodOptional<z.ZodNumber>;
        outputTokens: z.ZodOptional<z.ZodNumber>;
        cacheReadTokens: z.ZodOptional<z.ZodNumber>;
        cacheWriteTokens: z.ZodOptional<z.ZodNumber>;
        cost: z.ZodOptional<z.ZodNumber>;
        duration: z.ZodOptional<z.ZodNumber>;
        initiator: z.ZodOptional<z.ZodString>;
        apiCallId: z.ZodOptional<z.ZodString>;
        providerCallId: z.ZodOptional<z.ZodString>;
        quotaSnapshots: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodObject<{
            isUnlimitedEntitlement: z.ZodBoolean;
            entitlementRequests: z.ZodNumber;
            usedRequests: z.ZodNumber;
            usageAllowedWithExhaustedQuota: z.ZodBoolean;
            overage: z.ZodNumber;
            overageAllowedWithExhaustedQuota: z.ZodBoolean;
            remainingPercentage: z.ZodNumber;
            resetDate: z.ZodOptional<z.ZodDate>;
        }, "strip", z.ZodTypeAny, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }>>>;
    }, "strip", z.ZodTypeAny, {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    }, {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "assistant.usage";
    data: {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "assistant.usage";
    data: {
        model?: string | undefined;
        duration?: number | undefined;
        inputTokens?: number | undefined;
        outputTokens?: number | undefined;
        cacheReadTokens?: number | undefined;
        cacheWriteTokens?: number | undefined;
        cost?: number | undefined;
        initiator?: string | undefined;
        apiCallId?: string | undefined;
        providerCallId?: string | undefined;
        quotaSnapshots?: Record<string, {
            isUnlimitedEntitlement: boolean;
            entitlementRequests: number;
            usedRequests: number;
            usageAllowedWithExhaustedQuota: boolean;
            overage: number;
            overageAllowedWithExhaustedQuota: boolean;
            remainingPercentage: number;
            resetDate?: Date | undefined;
        }> | undefined;
    };
    timestamp: string;
    parentId: string | null;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"abort">;
    data: z.ZodObject<{
        reason: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        reason: string;
    }, {
        reason: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "abort";
    data: {
        reason: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "abort";
    data: {
        reason: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.user_requested">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        toolName: z.ZodString;
        arguments: z.ZodUnknown;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    }, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.user_requested";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.user_requested";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.execution_start">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        toolName: z.ZodString;
        arguments: z.ZodUnknown;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    }, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.execution_start";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.execution_start";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"tool.execution_partial_result">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        partialOutput: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        partialOutput: string;
    }, {
        toolCallId: string;
        partialOutput: string;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "tool.execution_partial_result";
    data: {
        toolCallId: string;
        partialOutput: string;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "tool.execution_partial_result";
    data: {
        toolCallId: string;
        partialOutput: string;
    };
    timestamp: string;
    parentId: string | null;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.execution_complete">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        success: z.ZodBoolean;
        isUserRequested: z.ZodOptional<z.ZodBoolean>;
        result: z.ZodOptional<z.ZodObject<{
            content: z.ZodString;
        }, "strip", z.ZodTypeAny, {
            content: string;
        }, {
            content: string;
        }>>;
        error: z.ZodOptional<z.ZodObject<{
            message: z.ZodString;
            code: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            message: string;
            code?: string | undefined;
        }, {
            message: string;
            code?: string | undefined;
        }>>;
        toolTelemetry: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    }, {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.execution_complete";
    data: {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.execution_complete";
    data: {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.started">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
        agentDisplayName: z.ZodString;
        agentDescription: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    }, {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.started";
    data: {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.started";
    data: {
        toolCallId: string;
        agentName: string;
        agentDisplayName: string;
        agentDescription: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.completed">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        agentName: string;
    }, {
        toolCallId: string;
        agentName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.completed";
    data: {
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.completed";
    data: {
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.failed">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        agentName: z.ZodString;
        error: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        error: string;
        toolCallId: string;
        agentName: string;
    }, {
        error: string;
        toolCallId: string;
        agentName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.failed";
    data: {
        error: string;
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.failed";
    data: {
        error: string;
        toolCallId: string;
        agentName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"custom_agent.selected">;
    data: z.ZodObject<{
        agentName: z.ZodString;
        agentDisplayName: z.ZodString;
        tools: z.ZodNullable<z.ZodArray<z.ZodString, "many">>;
    }, "strip", z.ZodTypeAny, {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    }, {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "custom_agent.selected";
    data: {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "custom_agent.selected";
    data: {
        tools: string[] | null;
        agentName: string;
        agentDisplayName: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"hook.start">;
    data: z.ZodObject<{
        hookInvocationId: z.ZodString;
        hookType: z.ZodString;
        input: z.ZodUnknown;
    }, "strip", z.ZodTypeAny, {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    }, {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "hook.start";
    data: {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "hook.start";
    data: {
        hookInvocationId: string;
        hookType: string;
        input?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"hook.end">;
    data: z.ZodObject<{
        hookInvocationId: z.ZodString;
        hookType: z.ZodString;
        output: z.ZodUnknown;
        success: z.ZodBoolean;
        error: z.ZodOptional<z.ZodObject<{
            message: z.ZodString;
            stack: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            message: string;
            stack?: string | undefined;
        }, {
            message: string;
            stack?: string | undefined;
        }>>;
    }, "strip", z.ZodTypeAny, {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    }, {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "hook.end";
    data: {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "hook.end";
    data: {
        success: boolean;
        hookInvocationId: string;
        hookType: string;
        error?: {
            message: string;
            stack?: string | undefined;
        } | undefined;
        output?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>, z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"system.message">;
    data: z.ZodObject<{
        content: z.ZodString;
        role: z.ZodEnum<["system", "developer"]>;
        name: z.ZodOptional<z.ZodString>;
        metadata: z.ZodOptional<z.ZodObject<{
            promptVersion: z.ZodOptional<z.ZodString>;
            variables: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "strip", z.ZodTypeAny, {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        }, {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        }>>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    }, {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "system.message";
    data: {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "system.message";
    data: {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>]>;

/**
 * All possible session event type strings
 */
export declare type SessionEventType = SessionEvent["type"];

export declare type SessionHandoffEvent = z.infer<typeof SessionHandoffEventSchema>;

/**
 * Remote session handed off to local
 */
declare const SessionHandoffEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.handoff">;
    data: z.ZodObject<{
        handoffTime: z.ZodString;
        sourceType: z.ZodEnum<["remote", "local"]>;
        repository: z.ZodOptional<z.ZodObject<{
            owner: z.ZodString;
            name: z.ZodString;
            branch: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            name: string;
            owner: string;
            branch?: string | undefined;
        }, {
            name: string;
            owner: string;
            branch?: string | undefined;
        }>>;
        context: z.ZodOptional<z.ZodString>;
        summary: z.ZodOptional<z.ZodString>;
        remoteSessionId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    }, {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.handoff";
    data: {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.handoff";
    data: {
        handoffTime: string;
        sourceType: "local" | "remote";
        summary?: string | undefined;
        context?: string | undefined;
        repository?: {
            name: string;
            owner: string;
            branch?: string | undefined;
        } | undefined;
        remoteSessionId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionIdleEvent = z.infer<typeof SessionIdleEventSchema>;

/**
 * Session initialization event (first line of JSONL file)
 */
declare const SessionIdleEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"session.idle">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "session.idle";
    data: {};
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "session.idle";
    data: {};
    timestamp: string;
    parentId: string | null;
}>;

export declare type SessionImportLegacyEvent = z.infer<typeof SessionImportLegacyEventSchema>;

/**
 * Legacy session imported (wraps entire legacy JSON)
 */
declare const SessionImportLegacyEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.import_legacy">;
    data: z.ZodObject<{
        legacySession: z.ZodObject<{
            sessionId: z.ZodString;
            startTime: z.ZodDate;
            chatMessages: z.ZodArray<z.ZodUnion<[z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"developer">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"system">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"image_url">;
                    image_url: z.ZodObject<{
                        url: z.ZodString;
                        detail: z.ZodOptional<z.ZodEnum<["auto", "low", "high"]>>;
                    }, "strip", z.ZodTypeAny, {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    }, {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                }, {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"input_audio">;
                    input_audio: z.ZodObject<{
                        data: z.ZodString;
                        format: z.ZodUnion<[z.ZodLiteral<"wav">, z.ZodLiteral<"mp3">]>;
                    }, "strip", z.ZodTypeAny, {
                        data: string;
                        format: "wav" | "mp3";
                    }, {
                        data: string;
                        format: "wav" | "mp3";
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                }, {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"file">;
                    file: z.ZodObject<{
                        file_date: z.ZodOptional<z.ZodString>;
                        file_id: z.ZodOptional<z.ZodString>;
                        filename: z.ZodOptional<z.ZodString>;
                    }, "strip", z.ZodTypeAny, {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    }, {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                }, {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                }>]>, "many">]>;
                role: z.ZodLiteral<"user">;
                name: z.ZodOptional<z.ZodString>;
            }, "strip", z.ZodTypeAny, {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            }, {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodOptional<z.ZodNullable<z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"refusal">;
                    refusal: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    refusal: string;
                    type: "refusal";
                }, {
                    refusal: string;
                    type: "refusal";
                }>]>, "many">]>>>;
                role: z.ZodLiteral<"assistant">;
                name: z.ZodOptional<z.ZodString>;
                refusal: z.ZodOptional<z.ZodNullable<z.ZodString>>;
                audio: z.ZodOptional<z.ZodNullable<z.ZodObject<{
                    id: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    id: string;
                }, {
                    id: string;
                }>>>;
                function_call: z.ZodOptional<z.ZodNullable<z.ZodObject<{
                    name: z.ZodString;
                    arguments: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    name: string;
                    arguments: string;
                }, {
                    name: string;
                    arguments: string;
                }>>>;
                tool_calls: z.ZodOptional<z.ZodArray<z.ZodUnion<[z.ZodObject<{
                    id: z.ZodString;
                    type: z.ZodLiteral<"function">;
                    function: z.ZodObject<{
                        name: z.ZodString;
                        arguments: z.ZodString;
                    }, "strip", z.ZodTypeAny, {
                        name: string;
                        arguments: string;
                    }, {
                        name: string;
                        arguments: string;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                }, {
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                }>, z.ZodObject<{
                    id: z.ZodString;
                    type: z.ZodLiteral<"custom">;
                    custom: z.ZodObject<{
                        name: z.ZodString;
                        input: z.ZodString;
                    }, "strip", z.ZodTypeAny, {
                        name: string;
                        input: string;
                    }, {
                        name: string;
                        input: string;
                    }>;
                }, "strip", z.ZodTypeAny, {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                }, {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                }>]>, "many">>;
            }, "strip", z.ZodTypeAny, {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            }, {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            }>, z.ZodObject<{
                content: z.ZodUnion<[z.ZodString, z.ZodArray<z.ZodObject<{
                    type: z.ZodLiteral<"text">;
                    text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    type: "text";
                    text: string;
                }, {
                    type: "text";
                    text: string;
                }>, "many">]>;
                role: z.ZodLiteral<"tool">;
                tool_call_id: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            }, {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            }>, z.ZodObject<{
                content: z.ZodNullable<z.ZodString>;
                role: z.ZodLiteral<"function">;
                name: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                content: string | null;
                role: "function";
                name: string;
            }, {
                content: string | null;
                role: "function";
                name: string;
            }>]>, "many">;
            timeline: z.ZodArray<z.ZodIntersection<z.ZodUnion<[z.ZodObject<{
                type: z.ZodLiteral<"copilot">;
                text: z.ZodString;
                isStreaming: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            }, {
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"error">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "error";
                text: string;
            }, {
                type: "error";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"info">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "info";
                text: string;
            }, {
                type: "info";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"user">;
                text: z.ZodString;
            }, "strip", z.ZodTypeAny, {
                type: "user";
                text: string;
            }, {
                type: "user";
                text: string;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"tool_call_requested">;
                callId: z.ZodString;
                name: z.ZodString;
                toolTitle: z.ZodOptional<z.ZodString>;
                intentionSummary: z.ZodNullable<z.ZodString>;
                arguments: z.ZodUnion<[z.ZodUnion<[z.ZodObject<{
                    command: z.ZodString;
                    description: z.ZodString;
                    timeout: z.ZodOptional<z.ZodNumber>;
                    sessionId: z.ZodOptional<z.ZodString>;
                    async: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    input: z.ZodString;
                    delay: z.ZodOptional<z.ZodNumber>;
                }, "strip", z.ZodTypeAny, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    delay: z.ZodNumber;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                    delay: number;
                }, {
                    sessionId: string;
                    delay: number;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                }, {
                    sessionId: string;
                }>]>, z.ZodDiscriminatedUnion<"command", [z.ZodObject<{
                    command: z.ZodLiteral<"view">;
                    path: z.ZodString;
                    view_range: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>>;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"create">;
                    path: z.ZodString;
                    file_text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "create";
                    file_text: string;
                }, {
                    path: string;
                    command: "create";
                    file_text: string;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"str_replace">;
                    path: z.ZodString;
                    new_str: z.ZodOptional<z.ZodString>;
                    old_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"insert">;
                    path: z.ZodString;
                    insert_line: z.ZodNumber;
                    new_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }>]>, z.ZodUnknown]>;
                partialOutput: z.ZodOptional<z.ZodString>;
                isHidden: z.ZodOptional<z.ZodBoolean>;
                isAlwaysExpanded: z.ZodOptional<z.ZodBoolean>;
                showNoContent: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }, {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }>, z.ZodObject<{
                type: z.ZodLiteral<"tool_call_completed">;
                callId: z.ZodString;
                name: z.ZodString;
                toolTitle: z.ZodOptional<z.ZodString>;
                intentionSummary: z.ZodNullable<z.ZodString>;
                result: z.ZodUnion<[z.ZodObject<{
                    type: z.ZodLiteral<"success">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"failure">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"rejected">;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "rejected";
                    markdown?: boolean | undefined;
                }, {
                    type: "rejected";
                    markdown?: boolean | undefined;
                }>, z.ZodObject<{
                    type: z.ZodLiteral<"denied">;
                    log: z.ZodString;
                    markdown: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                }, {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                }>]>;
                arguments: z.ZodUnion<[z.ZodUnion<[z.ZodObject<{
                    command: z.ZodString;
                    description: z.ZodString;
                    timeout: z.ZodOptional<z.ZodNumber>;
                    sessionId: z.ZodOptional<z.ZodString>;
                    async: z.ZodOptional<z.ZodBoolean>;
                }, "strip", z.ZodTypeAny, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }, {
                    command: string;
                    description: string;
                    sessionId?: string | undefined;
                    async?: boolean | undefined;
                    timeout?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    input: z.ZodString;
                    delay: z.ZodOptional<z.ZodNumber>;
                }, "strip", z.ZodTypeAny, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }, {
                    input: string;
                    sessionId: string;
                    delay?: number | undefined;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                    delay: z.ZodNumber;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                    delay: number;
                }, {
                    sessionId: string;
                    delay: number;
                }>, z.ZodObject<{
                    sessionId: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    sessionId: string;
                }, {
                    sessionId: string;
                }>]>, z.ZodDiscriminatedUnion<"command", [z.ZodObject<{
                    command: z.ZodLiteral<"view">;
                    path: z.ZodString;
                    view_range: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>>;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }, {
                    path: string;
                    command: "view";
                    view_range?: [number, number] | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"create">;
                    path: z.ZodString;
                    file_text: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "create";
                    file_text: string;
                }, {
                    path: string;
                    command: "create";
                    file_text: string;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"str_replace">;
                    path: z.ZodString;
                    new_str: z.ZodOptional<z.ZodString>;
                    old_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }, {
                    path: string;
                    command: "str_replace";
                    old_str: string;
                    new_str?: string | undefined;
                }>, z.ZodObject<{
                    command: z.ZodLiteral<"insert">;
                    path: z.ZodString;
                    insert_line: z.ZodNumber;
                    new_str: z.ZodString;
                }, "strip", z.ZodTypeAny, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }, {
                    path: string;
                    command: "insert";
                    new_str: string;
                    insert_line: number;
                }>]>, z.ZodUnknown]>;
                isHidden: z.ZodOptional<z.ZodBoolean>;
                isAlwaysExpanded: z.ZodOptional<z.ZodBoolean>;
                showNoContent: z.ZodOptional<z.ZodBoolean>;
            }, "strip", z.ZodTypeAny, {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }, {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }>]>, z.ZodObject<{
                id: z.ZodString;
                timestamp: z.ZodDate;
            }, "strip", z.ZodTypeAny, {
                id: string;
                timestamp: Date;
            }, {
                id: string;
                timestamp: Date;
            }>>, "many">;
            selectedModel: z.ZodOptional<z.ZodEnum<["claude-sonnet-4.5", "claude-haiku-4.5", "claude-opus-4.5", "claude-sonnet-4", "gpt-5.1-codex-max", "gpt-5.1-codex", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5.1-codex-mini", "gpt-5-mini", "gpt-4.1", "gemini-3-pro-preview"]>>;
        }, "strip", z.ZodTypeAny, {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        }, {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        }>;
        importTime: z.ZodString;
        sourceFile: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    }, {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.import_legacy";
    data: {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.import_legacy";
    data: {
        legacySession: {
            sessionId: string;
            startTime: Date;
            chatMessages: ({
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "developer";
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "system";
                name?: string | undefined;
            } | {
                content: string | ({
                    type: "text";
                    text: string;
                } | {
                    type: "image_url";
                    image_url: {
                        url: string;
                        detail?: "auto" | "low" | "high" | undefined;
                    };
                } | {
                    type: "input_audio";
                    input_audio: {
                        data: string;
                        format: "wav" | "mp3";
                    };
                } | {
                    type: "file";
                    file: {
                        file_date?: string | undefined;
                        file_id?: string | undefined;
                        filename?: string | undefined;
                    };
                })[];
                role: "user";
                name?: string | undefined;
            } | {
                role: "assistant";
                tool_calls?: ({
                    function: {
                        name: string;
                        arguments: string;
                    };
                    id: string;
                    type: "function";
                } | {
                    custom: {
                        name: string;
                        input: string;
                    };
                    id: string;
                    type: "custom";
                })[] | undefined;
                content?: string | ({
                    type: "text";
                    text: string;
                } | {
                    refusal: string;
                    type: "refusal";
                })[] | null | undefined;
                refusal?: string | null | undefined;
                audio?: {
                    id: string;
                } | null | undefined;
                function_call?: {
                    name: string;
                    arguments: string;
                } | null | undefined;
                name?: string | undefined;
            } | {
                content: string | {
                    type: "text";
                    text: string;
                }[];
                role: "tool";
                tool_call_id: string;
            } | {
                content: string | null;
                role: "function";
                name: string;
            })[];
            timeline: (({
                type: "copilot";
                text: string;
                isStreaming?: boolean | undefined;
            } | {
                type: "error";
                text: string;
            } | {
                type: "info";
                text: string;
            } | {
                type: "user";
                text: string;
            } | {
                type: "tool_call_requested";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                partialOutput?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            } | {
                result: {
                    type: "success";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "failure";
                    log: string;
                    markdown?: boolean | undefined;
                } | {
                    type: "rejected";
                    markdown?: boolean | undefined;
                } | {
                    type: "denied";
                    log: string;
                    markdown?: boolean | undefined;
                };
                type: "tool_call_completed";
                name: string;
                callId: string;
                intentionSummary: string | null;
                arguments?: unknown;
                toolTitle?: string | undefined;
                isHidden?: boolean | undefined;
                isAlwaysExpanded?: boolean | undefined;
                showNoContent?: boolean | undefined;
            }) & {
                id: string;
                timestamp: Date;
            })[];
            selectedModel?: "gpt-5" | "gpt-5-mini" | "gpt-4.1" | "claude-sonnet-4.5" | "claude-haiku-4.5" | "claude-opus-4.5" | "claude-sonnet-4" | "gpt-5.1-codex-max" | "gpt-5.1-codex" | "gpt-5.2" | "gpt-5.1" | "gpt-5.1-codex-mini" | "gemini-3-pro-preview" | undefined;
        };
        importTime: string;
        sourceFile: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionInfoEvent = z.infer<typeof SessionInfoEventSchema>;

/**
 * Informational message (for timeline/UI display)
 */
declare const SessionInfoEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.info">;
    data: z.ZodObject<{
        infoType: z.ZodString;
        message: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        message: string;
        infoType: string;
    }, {
        message: string;
        infoType: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.info";
    data: {
        message: string;
        infoType: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.info";
    data: {
        message: string;
        infoType: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * SessionManager interface
 */
export declare interface SessionManager<TSessionMetadata extends SessionMetadata = SessionMetadata, TSession extends Session<TSessionMetadata> = Session<TSessionMetadata>> {
    createSession(sessionOptions: SessionOptions): Promise<TSession>;
    getSession(options: {
        sessionId: string;
    }): Promise<TSession | undefined>;
    getLastSession(): Promise<TSession | undefined>;
    getLastSessionId(): Promise<string | undefined>;
    listSessions(): Promise<TSessionMetadata[]>;
    saveSession(session: TSession): Promise<void>;
    deleteSession(sessionId: string): Promise<void>;
    closeSession(sessionId: string): Promise<void>;
}

/**
 * SessionManager options - same as SessionOptions but used for creating the manager
 */
export declare type SessionManagerOptions = {
    logger?: RunnerLogger;
    integrationId?: string;
};

export declare interface SessionMetadata {
    readonly sessionId: string;
    readonly startTime: Date;
    readonly modifiedTime: Date;
    readonly summary?: string;
    readonly isRemote: boolean;
}

export declare type SessionModelChangeEvent = z.infer<typeof SessionModelChangeEventSchema>;

/**
 * Model selection changed mid-session
 */
declare const SessionModelChangeEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.model_change">;
    data: z.ZodObject<{
        previousModel: z.ZodOptional<z.ZodString>;
        newModel: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        newModel: string;
        previousModel?: string | undefined;
    }, {
        newModel: string;
        previousModel?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.model_change";
    data: {
        newModel: string;
        previousModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.model_change";
    data: {
        newModel: string;
        previousModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare interface SessionOptions extends Partial<SessionMetadata> {
    clientName?: string;
    model?: SupportedModel;
    integrationId?: string;
    /**
     * Custom API provider configuration (BYOK - Bring Your Own Key).
     * When set, bypasses Copilot API authentication and uses this provider instead.
     */
    provider?: ProviderConfig;
    featureFlags?: FeatureFlags;
    availableTools?: string[];
    excludedTools?: string[];
    executeToolsInParallel?: boolean;
    shellConfig?: ShellConfig;
    requestPermission?: (permissionRequest: PermissionRequest) => Promise<PermissionRequestResult>;
    skillDirectories?: string[];
    disabledSkills?: Set<string>;
    mcpServers?: Record<string, MCPServerConfig>;
    mcpHost?: McpHost;
    customAgents?: SweCustomAgent[];
    selectedCustomAgent?: SweCustomAgent;
    organizationCustomInstructions?: string;
    skipCustomInstructions?: boolean;
    systemMessage?: SystemMessageConfig;
    hooks?: QueryHooks;
    externalToolDefinitions?: ExternalToolDefinition[];
    externalToolDispatcher?: ExternalToolDispatcher;
    logger?: RunnerLogger;
    trajectoryFile?: string;
    eventsLogDirectory?: string;
    workingDirectory?: string;
    authInfo?: AuthInfo;
    copilotUrl?: string;
    enableStreaming?: boolean;
}

export declare type SessionResumeEvent = z.infer<typeof SessionResumeEventSchema>;

/**
 * Session resumed from disk
 */
declare const SessionResumeEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.resume">;
    data: z.ZodObject<{
        resumeTime: z.ZodString;
        eventCount: z.ZodNumber;
    }, "strip", z.ZodTypeAny, {
        resumeTime: string;
        eventCount: number;
    }, {
        resumeTime: string;
        eventCount: number;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.resume";
    data: {
        resumeTime: string;
        eventCount: number;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.resume";
    data: {
        resumeTime: string;
        eventCount: number;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionStartEvent = z.infer<typeof SessionStartEventSchema>;

/**
 * Session initialization event (first line of JSONL file)
 */
declare const SessionStartEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.start">;
    data: z.ZodObject<{
        sessionId: z.ZodString;
        version: z.ZodNumber;
        producer: z.ZodString;
        copilotVersion: z.ZodString;
        startTime: z.ZodString;
        selectedModel: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    }, {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.start";
    data: {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.start";
    data: {
        version: number;
        sessionId: string;
        producer: string;
        copilotVersion: string;
        startTime: string;
        selectedModel?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type SessionStartHook = (input: SessionStartHookInput) => Promise<SessionStartHookOutput | void>;

/**
 * Session start hook types
 */
export declare interface SessionStartHookInput extends BaseHookInput {
    source: "startup" | "resume" | "new";
    initialPrompt?: string;
}

export declare interface SessionStartHookOutput {
    additionalContext?: string;
    modifiedConfig?: Record<string, unknown>;
}

export declare type SessionTruncationEvent = z.infer<typeof SessionTruncationEventSchema>;

declare const SessionTruncationEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"session.truncation">;
    data: z.ZodObject<{
        tokenLimit: z.ZodNumber;
        preTruncationTokensInMessages: z.ZodNumber;
        preTruncationMessagesLength: z.ZodNumber;
        postTruncationTokensInMessages: z.ZodNumber;
        postTruncationMessagesLength: z.ZodNumber;
        tokensRemovedDuringTruncation: z.ZodNumber;
        messagesRemovedDuringTruncation: z.ZodNumber;
        performedBy: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    }, {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "session.truncation";
    data: {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "session.truncation";
    data: {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
        performedBy: string;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

declare class ShellConfig {
    /**
     * Used to vary behavior programmatically for different shell implementations.
     */
    readonly shellType: ShellType;
    /**
     * Used when describing the shell type to users or in prompts.
     */
    readonly displayName: string;
    /**
     * Name of a tool that invokes a shell command.
     */
    readonly shellToolName: string;
    /**
     * Name of a tool that reads output from a shell session.
     */
    readonly readShellToolName: string;
    /**
     * Name of a tool that sends input to a shell session.
     */
    readonly writeShellToolName: string;
    /**
     * Name of a tool that terminates a shell session.
     */
    readonly stopShellToolName: string;
    /**
     * Name of a tool that lists all active shell sessions.
     */
    readonly listShellsToolName: string;
    /**
     * Additional information to add to the tool description.
     */
    readonly descriptionLines: string[];
    /**
     * A function that assesses the safety of a script to be run in the shell.
     * The reason this exists as a pluggable abstraction is so that only the
     * CLI needs to take a compile-time dependency on tree-sitter, and CCA doesn't.
     */
    readonly assessScriptSafety: (script: string) => Promise<SafetyAssessment>;
    constructor(
    /**
     * Used to vary behavior programmatically for different shell implementations.
     */
    shellType: ShellType, 
    /**
     * Used when describing the shell type to users or in prompts.
     */
    displayName: string, 
    /**
     * Name of a tool that invokes a shell command.
     */
    shellToolName: string, 
    /**
     * Name of a tool that reads output from a shell session.
     */
    readShellToolName: string, 
    /**
     * Name of a tool that sends input to a shell session.
     */
    writeShellToolName: string, 
    /**
     * Name of a tool that terminates a shell session.
     */
    stopShellToolName: string, 
    /**
     * Name of a tool that lists all active shell sessions.
     */
    listShellsToolName: string, 
    /**
     * Additional information to add to the tool description.
     */
    descriptionLines: string[], 
    /**
     * A function that assesses the safety of a script to be run in the shell.
     * The reason this exists as a pluggable abstraction is so that only the
     * CLI needs to take a compile-time dependency on tree-sitter, and CCA doesn't.
     */
    assessScriptSafety?: (script: string) => Promise<SafetyAssessment>);
    withScriptSafetyAssessor(assessor: (shellType: ShellType, script: string) => Promise<SafetyAssessment>): ShellConfig;
    static readonly bash: ShellConfig;
    static readonly powerShell: ShellConfig;
}

/**
 * A permission request for executing shell commands.
 */
declare type ShellPermissionRequest = {
    readonly kind: "shell";
    /** The full command that the user is being asked to approve, e.g. `echo foo && find -exec ... && git push` */
    readonly fullCommandText: string;
    /** A concise summary of the user's intention, e.g. "Echo foo and find a file and then run git push" */
    readonly intention: string;
    /**
     * The commands that are being invoked in the shell invocation.
     *
     * As a special case, which might be better represented in the type system, if there were no parsed commands
     * e.g. `export VAR=value`, then this will have a single entry with identifier equal to the fullCommandText.
     */
    readonly commands: ReadonlyArray<Command>;
    /**
     * Possible file paths that the command might access.
     *
     * This is entirely heuristic, so it's pretty untrustworthy.
     */
    readonly possiblePaths: ReadonlyArray<PossiblePath>;
    /**
     * Possible URLs that the command might access.
     *
     * This is entirely heuristic, so it's pretty untrustworthy.
     */
    readonly possibleUrls: ReadonlyArray<PossibleUrl>;
    /**
     * Indicates whether any command in the script has redirection to write to a file.
     */
    readonly hasWriteFileRedirection: boolean;
    /**
     * If there are complicated constructs, then persistent approval is not supported.
     * e.g. `cat $(echo "foo")` should not be persistently approvable because it's hard
     * for the user to understand the implications.
     */
    readonly canOfferSessionApproval: boolean;
};

declare type ShellType = "bash" | "powershell";

/**
 * Simplified streaming chunk context containing only the essential delta information
 * needed by processors. This avoids the complexity of converting between different
 * API formats (e.g., Responses API to ChatCompletion chunks).
 *
 * @deprecated In the future, we will move to a model where the individual API clients emit Core Runtime events, instead of the current model where ChatCompletions are the defacto interface.
 * Please avoid adding new streaming chunk processors, and instead consider if now is the right time to fix the abstraction gap between the ChatCompletionsClient and the DerivedResponsesClient.
 * Talk to @jmoseley or @mrayermannmsft for more context.
 */
declare type StreamingChunkContext = {
    /**
     * The streaming ID of the message.
     */
    streamingId: string;
    /**
     * Text content delta from this chunk.
     */
    content?: string;
    /**
     * Arguments delta for the report_intent tool call. Processors can accumulate
     * these deltas to extract the intent once the JSON is complete.
     */
    reportIntentArguments?: string;
    /**
     * Approximate byte size of this chunk, calculated from content and all tool call data.
     */
    size: number;
};

/** List of supported model IDs in order of precedence to be used as the default */
declare const SUPPORTED_MODELS: readonly ["claude-sonnet-4.5", "claude-haiku-4.5", "claude-opus-4.5", "claude-sonnet-4", "gpt-5.1-codex-max", "gpt-5.1-codex", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5.1-codex-mini", "gpt-5-mini", "gpt-4.1", "gemini-3-pro-preview"];

declare type SupportedModel = (typeof SUPPORTED_MODELS)[number];

/**
 * Subset of src/types/clients/types.ts that is required to actually run
 * a custom agent.
 */
export declare type SweCustomAgent = {
    name: string;
    displayName: string;
    description: string;
    tools: string[] | null;
    prompt: () => Promise<string>;
    mcpServers?: Record<string, MCPServerConfig>;
    infer: boolean;
};

/**
 * Append mode: Use CLI foundation with optional appended content (default).
 */
declare interface SystemMessageAppendConfig {
    mode?: "append";
    /**
     * Additional instructions appended after SDK-managed sections.
     */
    content?: string;
}

/**
 * System message configuration for session creation.
 * - Append mode (default): SDK foundation + optional custom content
 * - Replace mode: Full control, caller provides entire system message
 */
declare type SystemMessageConfig = SystemMessageAppendConfig | SystemMessageReplaceConfig;

export declare type SystemMessageEvent = z.infer<typeof SystemMessageEventSchema>;

/**
 * System message/prompt
 */
declare const SystemMessageEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"system.message">;
    data: z.ZodObject<{
        content: z.ZodString;
        role: z.ZodEnum<["system", "developer"]>;
        name: z.ZodOptional<z.ZodString>;
        metadata: z.ZodOptional<z.ZodObject<{
            promptVersion: z.ZodOptional<z.ZodString>;
            variables: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "strip", z.ZodTypeAny, {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        }, {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        }>>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    }, {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "system.message";
    data: {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "system.message";
    data: {
        content: string;
        role: "developer" | "system";
        name?: string | undefined;
        metadata?: {
            promptVersion?: string | undefined;
            variables?: Record<string, unknown> | undefined;
        } | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * Replace mode: Use caller-provided system message entirely.
 * Removes all SDK guardrails including security restrictions.
 */
declare interface SystemMessageReplaceConfig {
    mode: "replace";
    /**
     * Complete system message content.
     * Replaces the entire SDK-managed system message.
     */
    content: string;
}

/**
 * Telemetry emitted by the runtime contains properties and metrics. These are non-sensitive pieces
 * of information. There are also restricted properties that must be used to store sensitive information.
 */
declare type Telemetry = {
    /**
     * Telemetry properties can be used to store string props.
     * WARNING: Do not put sensitive data here. Use restrictedProperties for that.
     */
    properties: Record<string, string | undefined>;
    /**
     * Restricted telemetry properties must be used to store sensitive string props. These props will only be available on the restricted kusto topics.
     * Nonnullable so it is harder to overlook.
     */
    restrictedProperties: Record<string, string | undefined>;
    /**
     * The name of the telemetry event associated with the emitted runtime event.
     */
    metrics: Record<string, number | undefined>;
};

/**
 * Alternatively telemetry can be emitted by an event which just contains telemetry. This is that type.
 *
 * You can use this type with our without generics. The generics help you to enforce what properties/metrics are on your event
 * more precisely and safely.
 */
declare type TelemetryEvent<EventT = string, TelemetryT extends Telemetry = Telemetry> = {
    kind: "telemetry";
    telemetry: EventTelemetry<EventT, TelemetryT>;
};

/** Represents a Token authentication information using in the SDK. */
declare type TokenAuthInfo = {
    readonly type: "token";
    readonly host: string;
    readonly token: string;
};

declare type Tool<CallbackT extends ToolCallback = ToolCallback> = ToolMetadata & {
    /**
     * The type of the tool. Defaults to "function" if not specified.
     * - "function": Standard function tool with JSON Schema input
     * - "custom": Custom tool with grammar-based input format
     */
    type?: "function" | "custom";
    /**
     * The input format for custom tools. Only used when type is "custom".
     */
    format?: CustomToolInputFormat;
    /**
     * A human readable string summary of what this command intends to do if executed.
     *
     * If not set, no summarised intention should be assumed by the caller.
     */
    summariseIntention?: (input: unknown) => string;
    callback: CallbackT;
    shutdown?: ToolShutdown;
    /**
     * Whether or not information about this tool is safe to send to telemetry without obfuscation.
     * - If `true`/`false`, then it will be assumed that all such information is safe/unsafe.
     * - If an object, then safety is determined per property.
     */
    safeForTelemetry?: {
        name: boolean;
        inputsNames: boolean;
    } | true;
};

/**
 * @param input The input to the tool
 * @param options Options for the tool, includes the standard `ToolCallbackOptions` as well as any additional options that were set for the tool in settings.
 */
declare type ToolCallback = (input: unknown, options?: ToolCallbackOptions) => Promise<ToolResult>;

declare type ToolCallbackOptions<OptionsT = {
    [key: string]: unknown;
}> = {
    /**
     * The ID of the LLM tool call which initiated this tool invocation.
     */
    toolCallId: string;
    truncationOptions?: {
        /**
         * The number of tokens that the tool's response should ideally be limited to.
         */
        tokenLimit: number;
        /**
         * A function to count the number of tokens in a string.
         */
        countTokens: (input: string) => number;
    };
    /**
     * A client that the tool can use to make chat completion calls.
     */
    client?: Client;
    /**
     * Other options specific to the tool. Passed in from settings.
     */
    toolOptions?: OptionsT;
    /**
     * Global runtime settings.
     */
    settings: RuntimeSettings;
    /**
     * An optional AbortSignal to allow cancellation of tool execution.
     */
    abortSignal?: AbortSignal;
};

export declare type ToolExecutionCompleteEvent = z.infer<typeof ToolExecutionCompleteEventSchema>;

/**
 * Tool execution completes (success or error)
 */
declare const ToolExecutionCompleteEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.execution_complete">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        success: z.ZodBoolean;
        isUserRequested: z.ZodOptional<z.ZodBoolean>;
        result: z.ZodOptional<z.ZodObject<{
            content: z.ZodString;
        }, "strip", z.ZodTypeAny, {
            content: string;
        }, {
            content: string;
        }>>;
        error: z.ZodOptional<z.ZodObject<{
            message: z.ZodString;
            code: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            message: string;
            code?: string | undefined;
        }, {
            message: string;
            code?: string | undefined;
        }>>;
        toolTelemetry: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    }, {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.execution_complete";
    data: {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.execution_complete";
    data: {
        toolCallId: string;
        success: boolean;
        result?: {
            content: string;
        } | undefined;
        error?: {
            message: string;
            code?: string | undefined;
        } | undefined;
        toolTelemetry?: Record<string, unknown> | undefined;
        parentToolCallId?: string | undefined;
        isUserRequested?: boolean | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

declare type ToolExecutionEvent = {
    kind: "tool_execution";
    turn: number;
    callId?: string;
    toolCallId: string;
    toolResult: ToolResultExpanded;
    durationMs: number;
};

export declare type ToolExecutionPartialResultEvent = z.infer<typeof ToolExecutionPartialResultEventSchema>;

/**
 * Tool execution partial result (streaming updates)
 * Note: These events have ephemeral: true and are NOT persisted to disk
 */
declare const ToolExecutionPartialResultEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
} & {
    type: z.ZodLiteral<"tool.execution_partial_result">;
    ephemeral: z.ZodLiteral<true>;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        partialOutput: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        partialOutput: string;
    }, {
        toolCallId: string;
        partialOutput: string;
    }>;
}, "strip", z.ZodTypeAny, {
    ephemeral: true;
    id: string;
    type: "tool.execution_partial_result";
    data: {
        toolCallId: string;
        partialOutput: string;
    };
    timestamp: string;
    parentId: string | null;
}, {
    ephemeral: true;
    id: string;
    type: "tool.execution_partial_result";
    data: {
        toolCallId: string;
        partialOutput: string;
    };
    timestamp: string;
    parentId: string | null;
}>;

export declare type ToolExecutionStartEvent = z.infer<typeof ToolExecutionStartEventSchema>;

/**
 * Tool execution begins
 */
declare const ToolExecutionStartEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.execution_start">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        toolName: z.ZodString;
        arguments: z.ZodUnknown;
    } & {
        parentToolCallId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    }, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.execution_start";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.execution_start";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
        parentToolCallId?: string | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * An event that is emitted by the `Client` for each tool message it will send back to the LLM.
 */
declare type ToolMessageEvent = {
    kind: "message";
    turn?: number;
    callId?: string;
    modelCall?: ModelCallParam;
    message: ChatCompletionToolMessageParam;
};

/**
 * Lightweight tool metadata used for system message building, token counting, and display.
 * Contains only the properties needed for these purposes, without execution callbacks.
 *
 * This is the base type that Tool extends. Functions that only need tool metadata
 * (like cliSystemMessage) should accept ToolMetadata[] to allow passing either
 * ToolMetadata[] or Tool[] without conversion.
 */
declare type ToolMetadata = {
    /**
     * Name used to identify the tool in prompts and tool calls.
     */
    name: string;
    /**
     * Optional namespaced name for the tool used for declarative filtering of tools.
     * e.g.: "playwright/navigate"
     */
    namespacedName?: string;
    /** Intended for UI and end-user contexts — optimized to be human-readable
     * and easily understood, even by those unfamiliar with domain-specific terminology.
     *
     * If not provided, the name should be used for display (except for Tool, where
     * annotations.title should be given precedence over using name, if present).
     */
    title?: string;
    /**
     * Description of what the tool does.
     */
    description: string;
    /**
     * JSON Schema for the tool's input.
     * Required for function tools, optional for custom tools.
     */
    input_schema?: any;
    /**
     * Optional instructions for how to use this tool effectively.
     * These instructions will be included in the system prompt's <tools> section.
     */
    instructions?: string;
};

declare type ToolResult = string | ToolResultExpanded;

declare type ToolResultExpanded<TelemetryT extends Telemetry = Telemetry> = {
    /**
     * The result to be given back to the LLM.
     *
     * If @see sessionLog is omitted, then this will be used as the session log.
     */
    textResultForLlm: string;
    /**
     * The result to be given back to the LLM. It can be either base64 encoded image or audio content.
     */
    binaryResultsForLlm?: BinaryResult[];
    /**
     * Whether or not the result should be considered a success, failure, or previously interrupted.
     * - `success`: The tool executed successfully and produced a valid result.
     * - `failure`: The tool encountered an error or did not produce a valid result.
     * - `rejected`: The tool call was rejected either because the user didn't want this call, or a previous dependent one.
     * - `denied`: The tool call was denied because the permissions service said no.
     */
    resultType: "success" | "failure" | "rejected" | "denied";
    /**
     * If there was any sort of error that caused the tool to fail, then a string representation of the error. Typically
     * only set if {@link resultType} is `'failure'`.
     */
    error?: string;
    /**
     * Specific telemetry for the tool. Will be sent back to the server by the agent.
     */
    toolTelemetry?: {
        properties?: TelemetryT["properties"];
        restrictedProperties?: TelemetryT["restrictedProperties"];
        metrics?: TelemetryT["metrics"];
    };
    /**
     * Well-formatted (typically Markdown) string that can be used to display the input/output of the tool invoked.
     *
     * (Optional) If omitted, the text result for the LLM will be used as the session log.
     */
    sessionLog?: string;
    /**
     * User messages to inject into the conversation history after this tool result.
     * These messages are added to the conversation and sent to the model, but can be
     * filtered from the timeline display based on their source.
     *
     * Use case: Skills inject their full content as user messages so the model
     * treats them as instructions to follow, while keeping the timeline clean.
     */
    newMessages?: InjectedUserMessage[];
};

/**
 * A callback to be called when the tool is shutting down. Gives the tool
 * a chance to clean things up, and return a telemetry event (if desired) which
 * will be emitted by the agent.
 */
declare type ToolShutdown = () => Promise<TelemetryEvent | void>;

export declare type ToolUserRequestedEvent = z.infer<typeof ToolUserRequestedEventSchema>;

/**
 * Tool user requested event
 */
declare const ToolUserRequestedEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"tool.user_requested">;
    data: z.ZodObject<{
        toolCallId: z.ZodString;
        toolName: z.ZodString;
        arguments: z.ZodUnknown;
    }, "strip", z.ZodTypeAny, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    }, {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "tool.user_requested";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "tool.user_requested";
    data: {
        toolCallId: string;
        toolName: string;
        arguments?: unknown;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

/**
 * Converts full Tool objects to lightweight ToolMetadata.
 * Used to create a safe-to-cache representation without callbacks.
 */
export declare function toToolMetadata(tools: Tool[]): ToolMetadata[];

declare type TruncationEvent = {
    kind: "history_truncated";
    turn: number;
    performedBy: string;
    truncateResult: {
        tokenLimit: number;
        preTruncationTokensInMessages: number;
        preTruncationMessagesLength: number;
        postTruncationTokensInMessages: number;
        postTruncationMessagesLength: number;
        tokensRemovedDuringTruncation: number;
        messagesRemovedDuringTruncation: number;
    };
};

declare type TurnEvent = {
    kind: "turn_started" | "turn_ended" | "turn_failed" | "turn_retry";
    model: string;
    modelInfo: object;
    turn: number;
    timestampMs: number;
    error?: string;
};

export declare type UpdatableSessionOptions = Omit<SessionOptions, "sessionId" | "startTime" | "modifiedTime" | "summary">;

/**
 * A permission request for accessing URLs.
 */
declare type UrlPermissionRequest = {
    readonly kind: "url";
    /** The intention, e.g. "Fetch web content" */
    readonly intention: string;
    /** The URL being accessed */
    readonly url: string;
};

/** Represents the user-based authentication information (OAuth). */
declare type UserAuthInfo = {
    readonly type: "user";
    readonly host: string;
    readonly login: string;
};

export declare type UserMessageEvent = z.infer<typeof UserMessageEventSchema>;

/**
 * An event that is emitted by the `Client` for each user message it adds to the middle of the conversation.
 */
declare type UserMessageEvent_2 = {
    kind: "message";
    turn?: number;
    callId?: string;
    modelCall?: ModelCallParam;
    message: ChatCompletionUserMessageParam;
    /**
     * The component which was the source of the user message.
     * - `jit-instruction`: The message was injected by something which adds automated instructions for the agent
     * - `command-{id}`: The message was injected as a result of a command with the given id
     * - `string`: Some other source
     */
    source?: string;
};

/**
 * User message with optional attachments
 */
declare const UserMessageEventSchema: z.ZodObject<{
    id: z.ZodString;
    timestamp: z.ZodString;
    parentId: z.ZodNullable<z.ZodString>;
    ephemeral: z.ZodOptional<z.ZodBoolean>;
} & {
    type: z.ZodLiteral<"user.message">;
    data: z.ZodObject<{
        content: z.ZodString;
        transformedContent: z.ZodOptional<z.ZodString>;
        attachments: z.ZodOptional<z.ZodArray<z.ZodObject<{
            type: z.ZodEnum<["file", "directory"]>;
            path: z.ZodString;
            displayName: z.ZodString;
        }, "strip", z.ZodTypeAny, {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }, {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }>, "many">>;
        source: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    }, {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    id: string;
    type: "user.message";
    data: {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}, {
    id: string;
    type: "user.message";
    data: {
        content: string;
        source?: string | undefined;
        transformedContent?: string | undefined;
        attachments?: {
            type: "file" | "directory";
            path: string;
            displayName: string;
        }[] | undefined;
    };
    timestamp: string;
    parentId: string | null;
    ephemeral?: boolean | undefined;
}>;

export declare type UserPromptSubmittedHook = (input: UserPromptSubmittedHookInput) => Promise<UserPromptSubmittedHookOutput | void>;

/**
 * User prompt submitted hook types
 */
export declare interface UserPromptSubmittedHookInput extends BaseHookInput {
    prompt: string;
}

export declare interface UserPromptSubmittedHookOutput {
    modifiedPrompt?: string;
    additionalContext?: string;
    suppressOutput?: boolean;
}

declare type WildcardEventHandler = (event: SessionEvent) => void;

/**
 * A permission request for writing to new or existing files.
 */
declare type WritePermissionRequest = {
    readonly kind: "write";
    /** The intention of the edit operation, e.g. "Edit file" or "Create file" */
    readonly intention: string;
    /** The name of the file being edited */
    readonly fileName: string;
    /** The diff of the changes being made */
    readonly diff: string;
};

export { }
