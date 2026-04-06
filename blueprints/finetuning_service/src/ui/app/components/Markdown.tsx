import React from 'react';
import { XMarkdown } from '@ant-design/x-markdown';

interface MarkdownProps {
  content: string;
  className?: string;
}

export const Markdown: React.FC<MarkdownProps> = ({ content, className }) => {
  return (
    <div className={className}>
      <XMarkdown
      >
        {content}
      </XMarkdown>
    </div>
  );
};
