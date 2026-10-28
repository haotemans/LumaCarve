export type Page = 'dashboard' | 'training' | 'generate' | 'flow' | 'gallery' | 'datasets' | 'models' | 'plugins' | 'history' | 'settings';
export type GalleryTab = 'artworks' | 'samples';
export type TaskState = 'training' | 'completed' | 'paused';

export interface OutputImage {
  id: string;
  name: string;
  kind: 'generation' | 'sample';
  taskId?: string;
  epoch?: number;
  step?: number;
  model: string;
  prompt: string;
  seed: number;
  size: string;
  steps: number;
  date: string;
  variant: number;
  favorite?: boolean;
  imageUrl?: string;
  imported?: boolean;
}

export interface TrainingTask {
  id: string;
  name: string;
  model: string;
  status: TaskState;
  epoch: number;
  totalEpochs: number;
  variant: number;
  date: string;
}

export interface DatasetImage {
  id: string;
  name: string;
  caption: string;
  variant: number;
  imageUrl?: string;
}

export interface Dataset {
  id: string;
  name: string;
  kind: string;
  images: DatasetImage[];
  accent: string;
}

export interface TrainingConfig {
  model: string;
  dataset: string;
  precision: string;
  epochs: number;
  rank: number;
  learningRate: string;
}

export type Notice = { id: number; text: string; tone?: 'success' | 'info' | 'warning' };
