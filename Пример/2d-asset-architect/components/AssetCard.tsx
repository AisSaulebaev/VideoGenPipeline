import React from 'react';
import { GeneratedAsset } from '../types';
import { Download, Maximize2, Repeat } from 'lucide-react';

interface AssetCardProps {
  asset: GeneratedAsset;
  onPreview: (asset: GeneratedAsset) => void;
  onRemix: (asset: GeneratedAsset) => void;
}

export const AssetCard: React.FC<AssetCardProps> = ({ asset, onPreview, onRemix }) => {
  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const link = document.createElement('a');
    link.href = asset.imageUrl;
    link.download = `asset-${asset.id}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleRemix = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRemix(asset);
  };

  return (
    <div 
      className="group relative rounded-xl overflow-hidden bg-slate-800 border border-slate-700 hover:border-indigo-500 transition-all duration-300 cursor-pointer shadow-lg hover:shadow-indigo-500/20"
      onClick={() => onPreview(asset)}
    >
      {/* 
        We use a square container for grid consistency, but object-contain 
        to ensure the whole asset is visible regardless of aspect ratio 
      */}
      <div className="aspect-square w-full relative bg-slate-900/50 flex items-center justify-center">
        <img 
          src={asset.imageUrl} 
          alt={asset.prompt} 
          className="w-full h-full object-contain"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
           <button 
            onClick={handleDownload}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white backdrop-blur-sm transition-colors"
            title="Download PNG"
          >
            <Download size={18} />
          </button>
          <button 
            onClick={handleRemix}
            className="p-2 bg-indigo-500/80 hover:bg-indigo-500 rounded-full text-white backdrop-blur-sm transition-colors"
            title="Remix (Use as Base)"
          >
            <Repeat size={18} />
          </button>
          <button 
            onClick={() => onPreview(asset)}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white backdrop-blur-sm transition-colors"
            title="View Fullsize"
          >
            <Maximize2 size={18} />
          </button>
        </div>
      </div>
      <div className="p-3">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">{asset.style}</p>
          <span className="text-[10px] bg-slate-700/50 px-1.5 py-0.5 rounded text-slate-400">
            {asset.aspectRatio || '1:1'}
          </span>
        </div>
        <p className="text-sm text-slate-200 line-clamp-2" title={asset.prompt}>{asset.prompt}</p>
      </div>
    </div>
  );
};