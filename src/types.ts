export type Role = 'user' | 'assistant';

export interface SourceCitation {
  id: string;
  title: string;
  url?: string;
  domain?: string;
  snippet?: string;
  sourceType?: string;
}

export interface OperatorUser {
  id: string;
  name: string;
  role: string;
  team: string;
  badge: string;
}

export const OPERATOR_USERS: OperatorUser[] = [
  { id: 'U-201', name: 'Michael Turner', role: 'Production Supervisor', team: 'Northeast Production', badge: 'Supervisor' },
  { id: 'U-202', name: 'Jessica Reed', role: 'Field Inspector', team: 'Northeast Production', badge: 'Inspector' },
  { id: 'U-203', name: 'Tyler Hughes', role: 'Field Operator', team: 'Northeast Production', badge: 'Operator' },
  { id: 'U-102', name: 'Jake Morales', role: 'Field Operator', team: 'Southwest Production', badge: 'Operator' },
  { id: 'U-401', name: 'Laura Simmons', role: 'HSE Officer', team: 'Health & Safety', badge: 'HSE' },
];

export interface GenUIComponentPayload {
  component: 'StatusCard' | 'DataTable' | 'LineChart' | 'BarChart' | 'GeoMap' | 'Heatmap' | 'ConflictAlert';
  title?: string;
  subtitle?: string;
  data?: any;
  [key: string]: any;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: Date | string;
  isStreaming?: boolean;
  isThinking?: boolean;
  thinkingContent?: string;
  sources?: SourceCitation[];
  followUps?: string[];
  error?: string;
  genuiPayload?: GenUIComponentPayload;
  attachments?: {
    name: string;
    size: string;
    type: string;
  }[];
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: Date | string;
  updatedAt: Date | string;
  messages: Message[];
  modelId: string;
  userId?: string;
}

export interface AIModel {
  id: string;
  name: string;
  badge: string;
  tagline: string;
  contextLength: string;
  iconName: string;
}

export type AccentColor = 'violet' | 'lime' | 'cyan';

export type Theme = 'dark' | 'light';
