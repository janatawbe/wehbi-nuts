import { useState } from 'react'
import { getStorefrontImageUrl } from '../../api/storefront'

interface ProductImageProps {
  src: string | null
  alt: string
  className?: string
}

/** A tasteful, on-brand placeholder for a product with no image yet (or
 * whose image fails to load) -- a soft warm gradient with a simple
 * original bean/leaf glyph, never a broken-image icon and never a
 * scraped/copyrighted photo. */
function ImageFallback({ alt, className }: { alt: string; className?: string }) {
  return (
    <div
      role="img"
      aria-label={alt}
      className={`flex items-center justify-center bg-gradient-to-br from-wehbi-gold-100 via-cream-deep to-wehbi-red-100 ${className ?? ''}`}
    >
      <svg viewBox="0 0 64 64" className="h-1/3 w-1/3 text-wehbi-red-300" fill="none" aria-hidden="true">
        <path
          d="M32 10c9 0 16 8 16 19s-8 25-16 25-16-14-16-25 7-19 16-19Z"
          fill="currentColor"
          opacity="0.5"
        />
        <path
          d="M32 6c3-4 8-4 10-1"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}

/** Renders a Product's stored image, or the fallback above when there is
 * none, or when the URL fails to load (e.g. a stale/moved media path) --
 * never a browser broken-image icon. */
export function ProductImage({ src, alt, className }: ProductImageProps) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return <ImageFallback alt={alt} className={className} />
  }

  return (
    <img
      src={getStorefrontImageUrl(src)}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className ?? ''}`}
    />
  )
}
