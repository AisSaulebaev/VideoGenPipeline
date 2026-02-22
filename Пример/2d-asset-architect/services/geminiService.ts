import { GoogleGenAI } from "@google/genai";
import { AssetStyle, AssetAspectRatio } from "../types";

export const getStyleSuffix = (style: AssetStyle): string => {
  switch (style) {
    case AssetStyle.PIXEL_ART:
      return "pixel art style, clean lines, sharp edges, retro game asset";
    case AssetStyle.FLAT_VECTOR:
      return "flat vector art, minimal details, clean colors, mobile game asset, white background";
    case AssetStyle.REALISTIC_TEXTURE:
      return "realistic texture, high fidelity, seamless pattern, PBR material";
    case AssetStyle.ISOMETRIC:
      return "isometric view, 3d render style, game sprite, isolated on black background";
    case AssetStyle.HAND_DRAWN:
      return "hand drawn sketch style, artistic, rough edges, concept art";
    default:
      return "";
  }
};

interface GenerateAssetOptions {
  style: AssetStyle;
  aspectRatio: AssetAspectRatio;
  referenceImageUrls?: string[];
}

export const generateAsset = async (prompt: string, options: GenerateAssetOptions): Promise<string> => {
  if (!process.env.API_KEY) {
    throw new Error("API Key is missing. Please check your environment configuration.");
  }

  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  
  const styleSuffix = getStyleSuffix(options.style);
  const parts: any[] = [];

  // Add reference images if they exist
  if (options.referenceImageUrls && options.referenceImageUrls.length > 0) {
    options.referenceImageUrls.forEach((url, index) => {
      try {
        const base64Data = url.split(',')[1];
        const mimeType = url.split(';')[0].split(':')[1];
        
        parts.push({
          inlineData: {
            mimeType: mimeType,
            data: base64Data
          }
        });
      } catch (e) {
        console.warn(`Failed to parse reference image ${index} data URL`, e);
      }
    });

    // Special instruction for multi-image context to ensure it generates an IMAGE, not text.
    const multiImageContext = options.referenceImageUrls.length > 1 
      ? " Combine the elements from these images into a single new asset." 
      : " Use this image as a direct reference for the new asset.";
      
    parts.push({ 
      text: `Generate a new game asset image. ${multiImageContext} Instructions: ${prompt}. Maintain the visual style and quality. ${styleSuffix}. IMPORTANT: Output ONLY the generated image.` 
    });
  } else {
    // Standard Text-to-Image logic
    parts.push({ text: `Generate a high-quality game asset image of: ${prompt}. ${styleSuffix}. IMPORTANT: Output ONLY the generated image.` });
  }

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash-image',
      contents: {
        parts: parts,
      },
      config: {
        imageConfig: {
          aspectRatio: options.aspectRatio,
        },
      },
    });

    if (!response.candidates || response.candidates.length === 0) {
      throw new Error("The model did not return any results. This might be due to safety filters or a temporary service issue.");
    }

    const candidate = response.candidates[0];

    // Check for safety blocks
    if (candidate.finishReason === 'SAFETY') {
      throw new Error("Request was blocked by safety filters. Try a different prompt or images (avoid logos with significant text or sensitive content).");
    }

    if (candidate.content && candidate.content.parts) {
      // Search for image data first
      for (const part of candidate.content.parts) {
        if (part.inlineData && part.inlineData.data) {
          return `data:${part.inlineData.mimeType || 'image/png'};base64,${part.inlineData.data}`;
        }
      }
      
      // If no image, check for text (which might be a refusal message)
      for (const part of candidate.content.parts) {
        if (part.text) {
          throw new Error(`Model Refusal: ${part.text}`);
        }
      }
    }

    throw new Error(`No image data found. Finish reason: ${candidate.finishReason || 'Unknown'}`);
  } catch (error: any) {
    console.error("Gemini API Error Detail:", error);
    // Return a user-friendly error
    if (error.message.includes("SAFETY")) {
        throw new Error("Content safety block triggered. Please try a different prompt or less complex images.");
    }
    throw error;
  }
};