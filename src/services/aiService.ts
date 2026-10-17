import { Message, SourceCitation } from '../types';

export interface SendMessageOptions {
  prompt: string;
  modelId: string;
  conversationHistory: Message[];
  userId?: string;
  conversationId?: string;
  onThinking?: () => void;
  onToken: (token: string, fullText: string) => void;
  onSources?: (sources: SourceCitation[]) => void;
  onFollowUps?: (followUps: string[]) => void;
  signal?: AbortSignal;
}

/**
 * ============================================================================
 * AI SERVICE LAYER - SWAPPABLE API CONNECTOR
 * ============================================================================
 * This module isolates the entire AI request/response streaming pipeline.
 * Currently, it simulates a hyper-realistic, token-by-token streaming AI response
 * complete with a thinking phase, Perplexity-style citations, and follow-ups.
 * 
 * ----------------------------------------------------------------------------
 * HOW TO SWAP IN A REAL BACKEND (OpenAI / Anthropic / FastAPI):
 * ----------------------------------------------------------------------------
 * 
 * [OPTION 1: FastAPI SSE Endpoint]
 * async function sendMessageRealFastAPI(options: SendMessageOptions) {
 *   const response = await fetch('http://localhost:8000/api/chat/stream', {
 *     method: 'POST',
 *     headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({
 *       prompt: options.prompt,
 *       model: options.modelId,
 *       history: options.conversationHistory,
 *     }),
 *     signal: options.signal,
 *   });
 *   
 *   const reader = response.body?.getReader();
 *   const decoder = new TextDecoder();
 *   let accumulated = '';
 *   
 *   while (reader) {
 *     const { done, value } = await reader.read();
 *     if (done) break;
 *     const chunk = decoder.decode(value);
 *     // Process Server-Sent Events (data: {...})
 *     accumulated += chunk;
 *     options.onToken(chunk, accumulated);
 *   }
 * }
 * 
 * [OPTION 2: OpenAI API (Direct or Proxied)]
 * async function sendMessageOpenAI(options: SendMessageOptions) {
 *   const response = await fetch('https://api.openai.com/v1/chat/completions', {
 *     method: 'POST',
 *     headers: {
 *       'Content-Type': 'application/json',
 *       'Authorization': `Bearer ${YOUR_OPENAI_API_KEY}`,
 *     },
 *     body: JSON.stringify({
 *       model: options.modelId === 'deepseek-r1' ? 'o3-mini' : 'gpt-4o',
 *       messages: [
 *         ...options.conversationHistory.map(m => ({ role: m.role, content: m.content })),
 *         { role: 'user', content: options.prompt }
 *       ],
 *       stream: true,
 *     }),
 *     signal: options.signal,
 *   });
 *   // Stream reader loop...
 * }
 * 
 * [OPTION 3: Anthropic Claude API]
 * async function sendMessageAnthropic(options: SendMessageOptions) {
 *   // Use Anthropic Messages API with stream: true
 * }
 * ============================================================================
 */

export async function sendMessage(options: SendMessageOptions): Promise<string> {
  const { prompt, conversationHistory, onThinking, onToken, signal, userId, conversationId } = options;

  if (onThinking) {
    onThinking();
  }

  // Try real FastAPI backend at http://localhost:8000/chat
  try {
    const messages = [
      ...conversationHistory
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: prompt },
    ];

    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages,
        stream: true,
        use_tools: true,
        user_id: userId || 'U-201',
        conversation_id: conversationId,
      }),
      signal,
    });

    if (response.ok) {
      const reader = response.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder('utf-8');
        let accumulated = '';
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('event:')) continue;
            if (trimmed.startsWith('data: ')) {
              const rawJson = trimmed.slice(6);
              try {
                const parsed = JSON.parse(rawJson);
                if (parsed.error) {
                  const errorMsg = `⚠️ Error: ${parsed.error.message || 'An error occurred during generation'}`;
                  accumulated = errorMsg;
                  onToken(errorMsg, accumulated);
                  return errorMsg;
                }
                if (parsed.token) {
                  accumulated += parsed.token;
                  onToken(parsed.token, accumulated);
                }
                if (parsed.done) {
                  if (!accumulated) {
                    const fallback = "No additional data records were returned for this query.";
                    onToken(fallback, fallback);
                    return fallback;
                  }
                  return accumulated;
                }
              } catch {
                // Ignore partial JSON chunks
              }
            }
          }
        }

        if (!accumulated) {
          const fallback = "No additional data records were returned for this query.";
          onToken(fallback, fallback);
          return fallback;
        }
        return accumulated;
      }
    } else {
      const errJson = await response.json().catch(() => ({}));
      const errMsg = errJson?.error?.message || `⚠️ Backend error (${response.status}): ${response.statusText}`;
      onToken(errMsg, errMsg);
      return errMsg;
    }
  } catch (err: any) {
    if (signal?.aborted) {
      throw new DOMException('Generation stopped by user', 'AbortError');
    }
    const errMsg = `⚠️ Unable to reach backend at http://localhost:8000: ${err.message || 'Connection failed'}. Please verify the FastAPI backend server is running.`;
    onToken(errMsg, errMsg);
    return errMsg;
  }

  return "No response received.";
}

async function sendMessageMock(options: SendMessageOptions): Promise<string> {
  const { prompt, onThinking, onToken, onSources, onFollowUps, signal } = options;

  await sleep(350, signal);

  // 2. Select contextual response based on prompt keywords
  const scenario = getContextualMock(prompt);

  // 3. Emit Mock Sources (Perplexity-style research grounding)
  if (onSources && scenario.sources) {
    onSources(scenario.sources);
  }

  // 4. Stream tokens word-by-word with natural cadence
  const words = scenario.markdown.split(' ');
  let accumulated = '';

  for (let i = 0; i < words.length; i++) {
    if (signal?.aborted) {
      throw new DOMException('Generation stopped by user', 'AbortError');
    }

    const word = words[i];
    const token = i === 0 ? word : ' ' + word;
    accumulated += token;
    onToken(token, accumulated);

    let delay = 22 + Math.floor(Math.random() * 20);
    if (word.endsWith('.') || word.endsWith('\n') || word.endsWith('?')) {
      delay += 40;
    }
    await sleep(delay, signal);
  }

  // 5. Emit Follow-up suggestions
  if (onFollowUps && scenario.followUps) {
    onFollowUps(scenario.followUps);
  }

  return accumulated;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      return reject(new DOMException('Aborted', 'AbortError'));
    }

    const timer = setTimeout(() => {
      resolve();
    }, ms);

    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

interface Scenario {
  markdown: string;
  sources: SourceCitation[];
  followUps: string[];
}

function getContextualMock(prompt: string): Scenario {
  const p = prompt.toLowerCase();

  if (p.includes('cache') || p.includes('redis') || p.includes('distributed') || p.includes('system design')) {
    return {
      sources: [
        { id: '1', title: 'Redis Architecture & Sentinel Guide', url: 'https://redis.io/docs/management/sentinel/', domain: 'redis.io' },
        { id: '2', title: 'Cache Invalidation at Scale', url: 'https://highscalability.com/cache-strategies', domain: 'highscalability.com' },
        { id: '3', title: 'Distributed Systems Patterns (O\'Reilly)', url: 'https://oreilly.com/library/distributed-systems', domain: 'oreilly.com' },
      ],
      markdown: `### Distributed Multi-Region Cache Architecture

To achieve sub-millisecond read latencies with multi-region fault tolerance, we decouple **edge reads** from **origin writes** using an active-active Redis cluster topology with asynchronous replication.

#### Key Architectural Pillars

1. **Local-First Reads**: Route clients to their nearest regional replica pool via Anycast DNS or Cloudflare Workers.
2. **Write-Through Invalidation**: Centralized mutation gateway pushes tombstone markers to a pub/sub event bus.
3. **Stampede Mitigation**: Employ probabilistic early expiration (XFetch algorithm) rather than hard TTL walls.

\`\`\`typescript
import { createClient } from 'redis';

interface CacheEntry<T> {
  data: T;
  computedAt: number;
  ttlSeconds: number;
}

export class ResilientCache {
  private client = createClient({ url: process.env.REDIS_URL });

  /**
   * Probabilistic Early Expiration (XFetch)
   * Prevents cache stampedes when hot keys expire under load
   */
  async getWithRecompute<T>(
    key: string,
    ttlSec: number,
    computeFn: () => Promise<T>,
    beta = 1.0
  ): Promise<T> {
    const raw = await this.client.get(key);
    if (raw) {
      const entry: CacheEntry<T> = JSON.parse(raw);
      const remainingTime = entry.ttlSeconds - (Date.now() - entry.computedAt) / 1000;
      
      // If early expiration condition triggers, refresh in background
      if (remainingTime > 0 && -(remainingTime) * Math.log(Math.random()) > beta) {
        this.refreshInBackground(key, ttlSec, computeFn);
      }
      return entry.data;
    }

    const freshData = await computeFn();
    await this.set(key, freshData, ttlSec);
    return freshData;
  }

  private async refreshInBackground<T>(key: string, ttl: number, fn: () => Promise<T>) {
    fn().then(data => this.set(key, data, ttl)).catch(console.error);
  }

  private async set<T>(key: string, data: T, ttlSeconds: number) {
    const payload: CacheEntry<T> = { data, computedAt: Date.now(), ttlSeconds };
    await this.client.setEx(key, ttlSeconds, JSON.stringify(payload));
  }
}
\`\`\`

#### Trade-Off Analysis

| Dimension | Single Region | Multi-Region Active/Passive | Multi-Region Active/Active |
| :--- | :--- | :--- | :--- |
| **P99 Read Latency** | 45ms - 180ms | 2ms - 8ms (local) | 1ms - 5ms (edge) |
| **Write Consistency** | Immediate (ACID) | Strong at primary | Eventual (CRDTs) |
| **Operational Overhead** | Low | Moderate | High (conflict resolution) |

> **Recommendation**: Start with an Active/Passive read-replica setup unless your global write concurrency demands multi-master CRDT replication.`,
      followUps: [
        'How does the XFetch probabilistic algorithm calculate optimal recomputation delta?',
        'What are the best practices for handling Redis cluster cross-slot keys?',
        'Can you show how to integrate this with Next.js edge runtime?',
      ],
    };
  }

  if (p.includes('memory') || p.includes('leak') || p.includes('debug') || p.includes('event')) {
    return {
      sources: [
        { id: '1', title: 'Node.js Memory Leak Diagnostic Guide', url: 'https://nodejs.org/en/docs/guides/diagnostics/memory', domain: 'nodejs.org' },
        { id: '2', title: 'V8 Engine Heap Snapshot Analysis', url: 'https://v8.dev/blog/heap-snapshots', domain: 'v8.dev' },
      ],
      markdown: `### Debugging Node.js Memory Leaks: Event Listeners & Closures

In long-running Node.js services, the most insidious leaks originate from **unbounded event listener registrations** where a short-lived request object is captured inside a callback attached to a long-lived singleton.

#### The Anti-Pattern: Retained Closure Scope

\`\`\`typescript
// ❌ LEAKING CODE: Every incoming HTTP request attaches a closure
// capturing the massive 'req' object to a process-wide emitter!
import { EventEmitter } from 'events';

const globalMetrics = new EventEmitter();

export function handleRequest(req: any, res: any) {
  const requestBuffer = Buffer.alloc(1024 * 512); // 512 KB payload

  // Event listener attaches forever; req & requestBuffer never get garbage collected!
  globalMetrics.on('tick', () => {
    console.log(\`Active request: \${req.id}, size: \${requestBuffer.length}\`);
  });

  res.end('OK');
}
\`\`\`

#### The Clean Solution: WeakRef or Explicit Teardown

\`\`\`typescript
// ✅ FIXED CODE: Use an AbortSignal or explicit teardown hook
import { EventEmitter } from 'events';

const globalMetrics = new EventEmitter();

export function handleRequestFixed(req: any, res: any) {
  const reqId = req.id; // Only extract primitive identifiers, not the whole req!
  
  const onTick = () => {
    console.log(\`Heartbeat for request: \${reqId}\`);
  };

  globalMetrics.on('tick', onTick);

  // Automatically detach listener when response finishes
  res.on('finish', () => {
    globalMetrics.off('tick', onTick);
  });

  res.end('OK');
}
\`\`\`

#### Verification Command
You can profile the process heap allocations in real-time with Node's native inspector:
\`\`\`bash
node --inspect --expose-gc app.js
# Then open chrome://inspect in Google Chrome and trigger heap snapshots
\`\`\`
`,
      followUps: [
        'How does WeakRef compare to FinalizationRegistry for cache cleanup?',
        'How can we detect leaked event emitters automatically in CI tests?',
      ],
    };
  }

  if (p.includes('pitch') || p.includes('seed') || p.includes('startup') || p.includes('investor')) {
    return {
      sources: [
        { id: '1', title: 'Y Combinator Seed Pitch Deck Template', url: 'https://www.ycombinator.com/library/2u-how-to-build-a-seed-round-pitch-deck', domain: 'ycombinator.com' },
        { id: '2', title: 'First Round Capital Seed Fundamentals', url: 'https://review.firstround.com', domain: 'firstround.com' },
      ],
      markdown: `### Seed Round Pitch: High-Conviction Structure

For modern AI developer tooling, seed investors index heavily on **technical pedigree, velocity of product iteration, and proprietary data moats**.

#### The 30-Second Elevator Pitch
> *"Engineers spend 40% of their sprints debugging distributed async systems. We built an AI verification layer that sits inside the compiler, eliminating race conditions before code ever reaches staging. In 8 weeks, 14,000 developers have installed our CLI with 62% weekly active retention."*

#### 10-Slide Deck Blueprint

1. **The Inevitable Shift**: What fundamental technological inflection point just happened? *(e.g. LLM context windows make full-codebase reasoning viable)*
2. **The Hidden Pain**: Quantify developer hours lost and cost center impact.
3. **The Product Engine**: Clean, cinematic 10-second product GIF showing magical UX.
4. **The Wedge**: How do you capture organic bottom-up adoption with zero enterprise sales friction?
5. **Early Metrics**: Installs, GitHub stars, Retention cohort curve (flattening is key).
6. **Defensibility**: Why can't the incumbent just copy this with an update next month?
7. **Business Model**: Open-source core $\\rightarrow$ Enterprise team security & private VPC.
8. **The Team**: Why are you uniquely equipped to solve this problem?
9. **The Ask**: Target raise (\$2.5M - \$3.5M) and concrete 18-month technical milestones.

> **Investor Tip**: Keep slides ultra-minimal. Less than 25 words per slide, large metrics, and live product demos always outperform dense prose.`,
      followUps: [
        'What metrics do Tier-1 seed VCs expect for developer tool retention?',
        'How should we structure open-source licensing to prevent cloud provider exploitation?',
      ],
    };
  }

  // Default scenario (General AI insight with structured markdown, code, and clarity)
  return {
    sources: [
      { id: '1', title: 'Modern UI/UX Architectural Patterns', url: 'https://developer.mozilla.org/en-US/docs/Web/Accessibility', domain: 'developer.mozilla.org' },
      { id: '2', title: 'React Performance & Rendering Optimizations', url: 'https://react.dev/learn/render-and-commit', domain: 'react.dev' },
      { id: '3', title: 'Designing Fluid Conversational Interfaces', url: 'https://arxiv.org/abs/2303.08774', domain: 'arxiv.org' },
    ],
    markdown: `### Understanding "${prompt}"

To examine this with depth and clarity, let's break it down into core principles, architectural mechanics, and practical implementation patterns.

#### Core Fundamentals
When designing reactive, state-driven user interfaces, maintaining strict separation between **presentation logic** and **streaming network transport** ensures optimal performance and maintainability:

1. **State Isolation**: Decouple incoming chunks from heavy re-render trees using micro-task batches.
2. **Visual Ergonomics**: Provide immediate perceptual feedback (skeleton pulse, typing indicators) before the first token arrives.
3. **Graceful Fallbacks**: Ensure interruptions, abort signals, and network hiccups preserve partial content.

\`\`\`typescript
// Clean streaming event handler pattern
export async function streamData(url: string, signal: AbortSignal) {
  const response = await fetch(url, { signal });
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    console.log('Received chunk:', chunk);
  }
}
\`\`\`

#### Key Takeaways
- **Responsiveness**: Always preserve user agency—users should be able to halt streaming or inspect sources at any time.
- **Hierarchy**: Maintain high information density without visual clutter through layered translucent surfaces and disciplined typography.
`,
    followUps: [
      'Can you expand on how to handle error boundary retries in this context?',
      'How would we implement optimistic UI updates for faster feedback?',
      'Show an end-to-end unit test for this streaming function.',
    ],
  };
}
