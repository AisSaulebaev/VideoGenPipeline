import React, { useState } from 'react';
import { AssetStyle, AssetAspectRatio } from '../types';
import { getStyleSuffix } from '../services/geminiService';
import { X, Copy, Check, Terminal } from 'lucide-react';

interface ApiCodeViewerProps {
  prompt: string;
  style: AssetStyle;
  aspectRatio: AssetAspectRatio;
  referenceImagesCount: number;
  onClose: () => void;
}

type Language = 'node' | 'python' | 'curl';

export const ApiCodeViewer: React.FC<ApiCodeViewerProps> = ({ 
  prompt, 
  style, 
  aspectRatio, 
  referenceImagesCount,
  onClose 
}) => {
  const [activeTab, setActiveTab] = useState<Language>('node');
  const [copied, setCopied] = useState(false);

  const styleSuffix = getStyleSuffix(style);
  const contextText = referenceImagesCount > 1 ? " Combine elements from images." : "";
  const finalPrompt = referenceImagesCount > 0 
    ? `Based on the provided images, ${prompt}.${contextText} ${styleSuffix}`
    : `Generate an image of a game asset: ${prompt}. ${styleSuffix}`;

  const getCode = (lang: Language) => {
    const imagesArray = Array(referenceImagesCount || 1).fill(null).map((_, i) => `{
        inlineData: {
          mimeType: 'image/png',
          data: 'BASE64_IMAGE_${i + 1}_HERE'
        }
      }`);

    if (lang === 'node') {
      return `import { GoogleGenAI } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const response = await ai.models.generateContent({
  model: 'gemini-2.5-flash-image',
  contents: {
    parts: [
      ${referenceImagesCount > 0 ? imagesArray.join(',\n      ') + ',' : ''}
      { text: "${finalPrompt.replace(/"/g, '\\"')}" }
    ]
  },
  config: {
    imageConfig: {
      aspectRatio: "${aspectRatio}"
    }
  }
});

const imageBase64 = response.candidates[0].content.parts.find(p => p.inlineData)?.inlineData.data;`;
    }

    if (lang === 'python') {
      return `from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ["API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[
        ${referenceImagesCount > 0 ? `types.Part.from_bytes(data=image_1_bytes, mime_type="image/png"),
        # ... repeat for each image` : ''}
        "${finalPrompt.replace(/"/g, '\\"')}"
    ],
    config=types.GenerateContentConfig(
        image_config=types.ImageGenerationConfig(
            aspect_ratio="${aspectRatio}"
        )
    )
)`;
    }

    if (lang === 'curl') {
      return `curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key=$API_KEY" \\
-H "Content-Type: application/json" \\
-X POST \\
-d '{
  "contents": [{
    "parts": [
      ${referenceImagesCount > 0 ? `{"inlineData": {"mimeType": "image/png", "data": "BASE64_1"}},` : ''}
      {"text": "${finalPrompt.replace(/"/g, '\\"')}"}
    ]
  }],
  "generationConfig": {
    "imageConfig": { "aspectRatio": "${aspectRatio}" }
  }
}'`;
    }

    return '';
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getCode(activeTab));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg">
              <Terminal size={20} className="text-indigo-400" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-100">API Multi-Image Code</h3>
              <p className="text-xs text-slate-400">Context: {referenceImagesCount} image(s)</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white"><X size={20} /></button>
        </div>
        <div className="flex border-b border-slate-800 bg-slate-950/50">
          {(['node', 'python', 'curl'] as Language[]).map((lang) => (
            <button key={lang} onClick={() => setActiveTab(lang)} className={`px-6 py-3 text-sm font-medium relative ${activeTab === lang ? 'text-indigo-400 bg-slate-900' : 'text-slate-400 hover:text-slate-200'}`}>
              {lang.toUpperCase()}
              {activeTab === lang && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-auto bg-slate-950 p-6 relative group font-mono text-sm">
          <pre className="text-slate-300"><code>{getCode(activeTab)}</code></pre>
          <button onClick={handleCopy} className="absolute top-4 right-4 p-2 bg-slate-800 border border-slate-700 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity">
            {copied ? <Check size={18} className="text-emerald-400" /> : <Copy size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
};