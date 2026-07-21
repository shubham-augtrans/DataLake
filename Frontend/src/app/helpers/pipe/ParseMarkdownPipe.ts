import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'parseMarkdown',
  standalone: true
})
export class ParseMarkdownPipe implements PipeTransform {
  transform(value: string): string {
    if (!value) return value;
    
    // Convert markdown tables to HTML
    let html = value;
    
    // Parse table
    const tableRegex = /\|(.+)\|\n\|(-+\|)+\n((\|.+\|\n)*)/g;
    html = html.replace(tableRegex, (match) => {
      const lines = match.trim().split('\n');
      let tableHtml = '<table class="markdown-table">';
      
      // Header
      if (lines[0]) {
        const headers = lines[0].split('|').map(h => h.trim()).filter(h => h);
        tableHtml += '<thead><tr>';
        headers.forEach(header => {
          tableHtml += `<th>${header}</th>`;
        });
        tableHtml += '</tr></thead>';
      }
      
      // Body
      tableHtml += '<tbody>';
      for (let i = 2; i < lines.length; i++) {
        if (lines[i].trim()) {
          const cells = lines[i].split('|').map(c => c.trim()).filter(c => c);
          tableHtml += '<tr>';
          cells.forEach(cell => {
            tableHtml += `<td>${cell}</td>`;
          });
          tableHtml += '</tr>';
        }
      }
      tableHtml += '</tbody></table>';
      
      return tableHtml;
    });
    
    // Convert **bold** to <strong>
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert *italic* to <em>
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Convert line breaks
    html = html.replace(/\n/g, '<br>');
    
    return html;
  }
}
