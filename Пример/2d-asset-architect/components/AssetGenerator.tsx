
import React, { useState, useEffect, useRef } from 'react';
import { AssetStyle, AssetAspectRatio, GeneratedAsset } from '../types';
import { generateAsset } from '../services/geminiService';
import { ApiCodeViewer } from './ApiCodeViewer';
import { Wand2, Loader2, AlertCircle, X, Image as ImageIcon, Upload, Code, Plus } from 'lucide-react';

interface AssetGeneratorProps {
  onAssetGenerated: (asset: GeneratedAsset) => void;
  baseAsset: GeneratedAsset | null;
  onClearBaseAsset: () => void;
}

export const AssetGenerator: React.FC<AssetGeneratorProps> = ({ onAssetGenerated, baseAsset, onClearBaseAsset }) => {
  const [prompt, setPrompt] = useState('Тайл пшеницы 256 на 256');
  const [style, setStyle] = useState<AssetStyle>(AssetStyle.REALISTIC_TEXTURE);
  const [aspectRatio, setAspectRatio] = useState<AssetAspectRatio>(AssetAspectRatio.SQUARE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceImages, setReferenceImages] = useState<string[]>([]);
  const [showApiCode, setShowApiCode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle Remix from gallery
  useEffect(() => {
    if (baseAsset) {
      setStyle(baseAsset.style);
      if (baseAsset.aspectRatio) {
        setAspectRatio(baseAsset.aspectRatio);
      }
      // Add remixed image to the list if not already there
      if (!referenceImages.includes(baseAsset.imageUrl)) {
        setReferenceImages(prev => [baseAsset.imageUrl, ...prev]);
      }
    }
  }, [baseAsset]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newImages: string[] = [];
      let processed = 0;

      // Cast to File[] to ensure 'file' is not 'unknown'
      (Array.from(files) as File[]).forEach(file => {
        // Fix: Property 'type' exists on 'File'
        if (!file.type.startsWith('image/')) return;
        
        const reader = new FileReader();
        reader.onloadend = () => {
          newImages.push(reader.result as string);
          processed++;
          if (processed === files.length) {
            setReferenceImages(prev => [...prev, ...newImages]);
            setError(null);
            if (fileInputRef.current) fileInputRef.current.value = '';
          }
        };
        // Fix: 'file' is now correctly typed as 'Blob' (via File)
        reader.readAsDataURL(file);
      });
    }
  };

  const removeImage = (index: number) => {
    const removed = referenceImages[index];
    setReferenceImages(prev => prev.filter((_, i) => i !== index));
    if (baseAsset && removed === baseAsset.imageUrl) {
      onClearBaseAsset();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const imageUrl = await generateAsset(prompt, {
        style, 
        aspectRatio,
        referenceImageUrls: referenceImages
      });
      
      const newAsset: GeneratedAsset = {
        id: crypto.randomUUID(),
        imageUrl,
        prompt,
        style,
        aspectRatio,
        timestamp: Date.now(),
      };

      onAssetGenerated(newAsset);
    } catch (err: any) {
      setError(err.message || "Failed to generate asset.");
    } finally {
      setLoading(false);
    }
  };

  const getAspectRatioLabel = (ratio: AssetAspectRatio) => {
    switch (ratio) {
      case AssetAspectRatio.SQUARE: return 'Square (1:1)';
      case AssetAspectRatio.LANDSCAPE: return 'Landscape (16:9)';
      case AssetAspectRatio.PORTRAIT: return 'Portrait (9:16)';
      case AssetAspectRatio.WIDE: return 'Wide (4:3)';
      case AssetAspectRatio.TALL: return 'Tall (3:4)';
      default: return ratio;
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto mb-12">
      <div className="bg-slate-800/50 backdrop-blur-md border border-slate-700 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        
        {/* Reference Images List */}
        <div className="mb-6 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-slate-300">Reference Images ({referenceImages.length})</h4>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileUpload} 
              accept="image/*" 
              multiple
              className="hidden"
            />
            <button 
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-xs flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              <Plus size={14} /> Add More
            </button>
          </div>

          {referenceImages.length > 0 ? (
            <div className="flex flex-wrap gap-3 p-3 bg-slate-900/50 border border-slate-700/50 rounded-xl">
              {referenceImages.map((img, idx) => (
                <div key={idx} className="relative group h-20 w-20 rounded-lg overflow-hidden border border-slate-700 bg-slate-950">
                  <img src={img} className="h-full w-full object-cover" alt={`Ref ${idx}`} />
                  <button 
                    onClick={() => removeImage(idx)}
                    className="absolute top-1 right-1 p-1 bg-black/60 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-8 border-2 border-dashed border-slate-700 rounded-xl flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-slate-400 hover:border-slate-600 transition-all bg-slate-900/20"
            >
              <Upload size={24} />
              <span className="text-sm">Upload context images (logo, style, base)</span>
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="-mt-2">
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="prompt" className="text-sm font-medium text-slate-300">
                Instructions for Gemini
              </label>
              <button 
                type="button" 
                onClick={() => setShowApiCode(true)}
                className="text-xs flex items-center gap-1.5 text-slate-500 hover:text-indigo-400 transition-colors"
                title="View API Code"
              >
                <Code size={14} />
                API
              </button>
            </div>
            <div className="relative">
              <textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={referenceImages.length > 0
                  ? "Describe how to combine these images (e.g., 'Place the logo from the second image onto the box in the first image')..."
                  : "Describe your asset (e.g., 'Golden wheat tile, top down view')..."
                }
                className="w-full h-32 bg-slate-900 border border-slate-700 rounded-xl p-4 text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none transition-all"
              />
              <div className="absolute bottom-4 right-4 text-xs text-slate-500">
                {prompt.length} chars
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Art Style
              </label>
              <div className="relative">
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value as AssetStyle)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none appearance-none cursor-pointer"
                >
                  {Object.values(AssetStyle).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
                </div>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Format / Resolution
              </label>
              <div className="relative">
                <select
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(e.target.value as AssetAspectRatio)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none appearance-none cursor-pointer"
                >
                  {Object.values(AssetAspectRatio).map((r) => (
                    <option key={r} value={r}>{getAspectRatioLabel(r)}</option>
                  ))}
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className={`w-full py-3 px-6 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all ${
                loading || !prompt.trim()
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white hover:shadow-lg hover:shadow-indigo-500/25'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Generating...
                </>
              ) : (
                <>
                  <Wand2 size={20} />
                  {referenceImages.length > 0 ? "Generate from References" : "Generate Asset"}
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400">
            <AlertCircle size={20} className="mt-0.5 shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        )}

        {showApiCode && (
          <ApiCodeViewer 
            prompt={prompt}
            style={style}
            aspectRatio={aspectRatio}
            referenceImagesCount={referenceImages.length}
            onClose={() => setShowApiCode(false)}
          />
        )}
      </div>
    </div>
  );
};
