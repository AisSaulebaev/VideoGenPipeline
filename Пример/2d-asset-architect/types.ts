export interface GeneratedAsset {
  id: string;
  imageUrl: string;
  prompt: string;
  style: AssetStyle;
  aspectRatio: AssetAspectRatio;
  timestamp: number;
}

export enum AssetStyle {
  PIXEL_ART = 'Pixel Art',
  FLAT_VECTOR = 'Flat Vector',
  REALISTIC_TEXTURE = 'Realistic Texture',
  ISOMETRIC = 'Isometric',
  HAND_DRAWN = 'Hand Drawn',
  NONE = 'No Style'
}

export enum AssetAspectRatio {
  SQUARE = '1:1',
  LANDSCAPE = '16:9',
  PORTRAIT = '9:16',
  WIDE = '4:3',
  TALL = '3:4'
}

export interface GenerationConfig {
  prompt: string;
  style: AssetStyle;
  aspectRatio: AssetAspectRatio;
}