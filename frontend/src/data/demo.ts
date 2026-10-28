import type { Dataset, OutputImage, TrainingTask } from '../types';

export const models = ['Anima Base 1.0 2B', 'MOSS-Image', 'Krea 2 RAW'];

export const tasks: TrainingTask[] = [
  { id: 'task-001', name: 'Hoshino · Character LoRA', model: 'Anima Base 1.0 2B', status: 'training', epoch: 8, totalEpochs: 20, variant: 2, date: '2026-10-29' },
  { id: 'task-002', name: 'Moonlit Bloom · Style', model: 'MOSS-Image', status: 'completed', epoch: 12, totalEpochs: 12, variant: 5, date: '2026-10-28' },
  { id: 'task-003', name: 'Aurora · Outfit Study', model: 'Anima Base 1.0 2B', status: 'paused', epoch: 4, totalEpochs: 16, variant: 7, date: '2026-10-27' },
  { id: 'task-004', name: 'Pastel Reverie', model: 'Krea 2 RAW', status: 'completed', epoch: 6, totalEpochs: 6, variant: 9, date: '2026-10-26' },
];

const descriptions = [
  'A silver-haired anime girl in moonlit blue, delicate embroidery, soft ethereal lighting, finely detailed illustration.',
  'A young girl beside a sunlit window, flowing hair, warm afternoon light, intricate floral decoration.',
  'An elegant fantasy character beneath glowing stars, cinematic violet tones, intricate outfit details.',
  'Portrait of a fantasy character with a ribbon, wistful eyes, luminous atmosphere and painterly colors.',
  'A girl in a flower garden at dawn, airy composition, pastel petals and dreamy sky.',
  'A celestial traveler on a rooftop, gentle blue twilight and atmospheric perspective.',
];

export const initialOutputs: OutputImage[] = [
  ...Array.from({ length: 14 }, (_, i): OutputImage => ({
    id: 'gen-' + String(i + 1).padStart(3, '0'),
    name: 'lumacarve_' + String(i + 1).padStart(4, '0') + '.png',
    kind: 'generation',
    model: models[i % 3],
    prompt: descriptions[i % descriptions.length],
    seed: 724190 + i * 1741,
    size: i % 3 === 0 ? '1024 × 1536' : i % 3 === 1 ? '1024 × 1024' : '1536 × 1024',
    steps: 24 + (i % 4) * 4,
    date: '2026-10-' + String(29 - Math.floor(i / 5)).padStart(2, '0'),
    variant: i + 1,
    favorite: i === 2 || i === 6,
  })),
  ...tasks.flatMap((task, t) => Array.from({ length: task.epoch + 1 }, (_, epoch): OutputImage => ({
    id: task.id + '-e' + epoch,
    name: epoch === 0 ? 'step_000000.png' : 'epoch_' + String(epoch).padStart(4, '0') + '.png',
    kind: 'sample',
    taskId: task.id,
    epoch,
    step: epoch * 100,
    model: task.model,
    prompt: 'Fixed validation prompt. ' + descriptions[t % descriptions.length],
    seed: 420000 + t * 77,
    size: '1024 × 1024',
    steps: 28,
    date: task.date,
    variant: task.variant + Math.min(epoch, 5),
  }))),
];

export const initialDatasets: Dataset[] = [
  {
    id: 'ds-001', name: 'Hoshino · Character', kind: '角色 LoRA', accent: '#6b87ff',
    images: Array.from({ length: 12 }, (_, i) => ({
      id: 'char-' + i,
      name: 'hoshino_' + String(i + 1).padStart(3, '0') + '.png',
      caption: 'A silver-haired character with blue eyes, wearing an ornate dark uniform, soft natural light, finely detailed illustration.',
      variant: i + 2,
    })),
  },
  {
    id: 'ds-002', name: 'Moonlit Bloom', kind: '画风 LoRA', accent: '#bd82e7',
    images: Array.from({ length: 8 }, (_, i) => ({
      id: 'style-' + i,
      name: 'style_' + String(i + 1).padStart(3, '0') + '.png',
      caption: 'Dreamy anime illustration, luminous gradients, delicate linework, expressive lighting, painterly background.',
      variant: i + 5,
    })),
  },
  {
    id: 'ds-003', name: 'Aurora · Wardrobe', kind: '服饰 LoRA', accent: '#63c9c4',
    images: Array.from({ length: 6 }, (_, i) => ({
      id: 'outfit-' + i,
      name: 'outfit_' + String(i + 1).padStart(3, '0') + '.png',
      caption: 'A fantasy outfit with layered fabric, ribbon details and metallic ornaments, neutral backdrop.',
      variant: i + 9,
    })),
  },
];
