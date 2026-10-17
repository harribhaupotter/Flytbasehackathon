import { AccentColor, AIModel } from '../types';

export interface AccentTheme {
  id: AccentColor;
  label: string;
  colorHex: string;
  cssVars: {
    '--accent-color': string;
    '--accent-hover': string;
    '--accent-muted': string;
    '--accent-glow': string;
    '--accent-fg': string;
    '--accent-ring': string;
  };
}

export const ACCENT_THEMES: Record<AccentColor, AccentTheme> = {
  violet: {
    id: 'violet',
    label: 'Electric Violet',
    colorHex: '#8B5CF6',
    cssVars: {
      '--accent-color': '#8B5CF6',
      '--accent-hover': '#7C3AED',
      '--accent-muted': 'rgba(139, 92, 246, 0.15)',
      '--accent-glow': 'rgba(139, 92, 246, 0.35)',
      '--accent-fg': '#FFFFFF',
      '--accent-ring': 'rgba(139, 92, 246, 0.4)',
    },
  },
  lime: {
    id: 'lime',
    label: 'Electric Lime',
    colorHex: '#CCFF00',
    cssVars: {
      '--accent-color': '#CCFF00',
      '--accent-hover': '#B8E600',
      '--accent-muted': 'rgba(204, 255, 0, 0.15)',
      '--accent-glow': 'rgba(204, 255, 0, 0.30)',
      '--accent-fg': '#0A0A0E',
      '--accent-ring': 'rgba(204, 255, 0, 0.45)',
    },
  },
  cyan: {
    id: 'cyan',
    label: 'Cyber Cyan',
    colorHex: '#06B6D4',
    cssVars: {
      '--accent-color': '#06B6D4',
      '--accent-hover': '#0891B2',
      '--accent-muted': 'rgba(6, 182, 212, 0.15)',
      '--accent-glow': 'rgba(6, 182, 212, 0.35)',
      '--accent-fg': '#FFFFFF',
      '--accent-ring': 'rgba(6, 182, 212, 0.4)',
    },
  },
};

export const AVAILABLE_MODELS: AIModel[] = [
  {
    id: 'gemini-3.8-flash',
    name: 'Gemini 3.8 Flash',
    badge: 'High Speed',
    tagline: 'High quota, sub-second latency, robust multi-tool synthesis',
    contextLength: '128k',
    iconName: 'Zap',
  },
  {
    id: 'gemma-4-26b-a4b-it',
    name: 'Gemma 4 (26B)',
    badge: 'Recommended',
    tagline: 'Fast reasoning, local/cloud tool calling via MCP',
    contextLength: '64k',
    iconName: 'Cpu',
  },
  {
    id: 'gemma-4-31b-it',
    name: 'Gemma 4 (31B)',
    badge: 'High Reasoning',
    tagline: 'Deep domain analysis and multi-source synthesis',
    contextLength: '64k',
    iconName: 'Cpu',
  },
  {
    id: 'mock',
    name: 'Mock Copilot Engine',
    badge: 'Offline Test',
    tagline: 'Zero-latency offline test mock',
    contextLength: '32k',
    iconName: 'Code',
  },
];

export interface StarterSuggestion {
  title: string;
  subtitle: string;
  prompt: string;
  icon: string;
  tag: string;
}

export const STARTER_SUGGESTIONS: StarterSuggestion[] = [
  {
    title: 'WELL-0001 Live Status',
    subtitle: 'Check thermal delta & planned shut-in notes',
    prompt: 'Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card.',
    icon: 'Layers',
    tag: 'Status Card',
  },
  {
    title: 'NE Block 8 Idle Wells',
    subtitle: 'Inspect non-producing wells with root causes',
    prompt: 'Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.',
    icon: 'Bug',
    tag: 'Table',
  },
  {
    title: 'WELL-0001 13-Week Trend',
    subtitle: 'Wellhead vs air temp with downtime bands',
    prompt: 'Show a line chart of WELL-0001\'s wellhead temperature against air temperature for the last 13 weeks, and mark when it was not producing oil.',
    icon: 'Atom',
    tag: 'Line Chart',
  },
  {
    title: 'NE Block 8 Recent Spills',
    subtitle: 'Interactive pad locator and spill volumes',
    prompt: 'Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.',
    icon: 'Sparkles',
    tag: 'Geo Map',
  },
];
