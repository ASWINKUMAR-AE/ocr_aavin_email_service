import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App, { LineEditor } from './App';
import { effectiveText } from './api';

describe('review workflow', () => {
  it('preserves explicit empty corrections', () => {
    expect(effectiveText({raw_text:'தமிழ்', corrected_text:''})).toBe('');
  });
  it('saves exact Unicode and review state without substituting digits', async () => {
    const save = vi.fn().mockResolvedValue();
    render(<LineEditor line={{id:'0:0',reading_order:0,raw_text:'தமிழ் 001',corrected_text:null,reviewed:false,confidence:.5}} selected={false} onSelect={() => {}} onSave={save} history={[]}/>);
    fireEvent.change(screen.getByLabelText('Correct line 1'),{target:{value:'தமிழ் 000000000001'}});
    fireEvent.click(screen.getByLabelText('Reviewed'));
    fireEvent.click(screen.getByText('Save changes'));
    await waitFor(() => expect(save).toHaveBeenCalledWith('தமிழ் 000000000001', true));
    expect(screen.getByText('50% confidence')).toBeInTheDocument();
  });
  it('shows actionable backend failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Offline')));
    render(<App/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable');
    vi.unstubAllGlobals();
  });
  it('retains unsaved text when another line causes a document refresh', () => {
    const line = {id:'0:0',reading_order:0,raw_text:'sample',corrected_text:null,reviewed:false,confidence:.8};
    const props = {selected:false,onSelect:()=>{},onSave:()=>{},history:[]};
    const {rerender} = render(<LineEditor line={line} {...props}/>);
    fireEvent.change(screen.getByLabelText('Correct line 1'),{target:{value:'my correction'}});
    rerender(<LineEditor line={{...line}} {...props}/>);
    expect(screen.getByLabelText('Correct line 1')).toHaveValue('my correction');
  });
});
