import { BlocksRenderer } from '@strapi/blocks-react-renderer';

interface RichTextRendererProps {
  content: unknown;
}

export function RichTextRenderer({ content }: RichTextRendererProps) {
  if (!content) return null;

  return (
    <div className="prose prose-gray max-w-none prose-headings:font-bold prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline">
      <BlocksRenderer
        content={content as Parameters<typeof BlocksRenderer>[0]['content']}
      />
    </div>
  );
}
