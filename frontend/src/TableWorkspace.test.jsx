import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import TableWorkspace, { CellEditor, parseEdges } from './TableWorkspace';
import { rowText } from './App';

afterEach(() => vi.unstubAllGlobals());

const cell = {row:0,column:0,text:'தமிழ் 001',raw_text:'தமிழ் 001',reviewed:false,source_ids:['0:0'],warnings:[],polygon:[[0,20],[100,20],[100,100],[0,100]]};
const table = {revision:0,x_edges:[0,100],y_edges:[20,100],columns:[{name:'Name',kind:'text'}],rows:[[cell]],history:[],overrides:{},unassigned_ids:[]};
const doc = {id:'sample',pages:[{index:0,width:100,height:100}]};

it('groups full text by visual row instead of one box per newline', () => {
  expect(rowText([{row_index:0,raw_text:'left'},{row_index:0,raw_text:'right'},{row_index:1,raw_text:'next'}])).toBe('left\tright\nnext');
});

it('saves exact cell corrections and explicit review state', async () => {
  const onSave=vi.fn();
  render(<CellEditor cell={cell} column={{name:'Name'}} history={[]} onDirty={()=>{}} busy={false} onSave={onSave}/>);
  fireEvent.change(screen.getByLabelText('Cell text'),{target:{value:'000000000001'}});
  fireEvent.click(screen.getByLabelText('Verified against image'));
  fireEvent.click(screen.getByText('Save cell'));
  expect(onSave).toHaveBeenCalledWith('000000000001',true);
  expect(screen.getByText('தமிழ் 001')).toBeInTheDocument();
});

it('requires saving a suggested layout before exporting', async () => {
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>table}).mockResolvedValueOnce({ok:true,json:async()=>({...table,revision:1})});
  vi.stubGlobal('fetch',fetch);
  render(<TableWorkspace doc={doc} pageIndex={0} onBack={()=>{}}/>);
  await screen.findByText('Save table layout');
  expect(screen.getByText('XLSX')).not.toHaveAttribute('href');
  fireEvent.click(screen.getByText('Save table layout'));
  await waitFor(()=>expect(screen.getByText('XLSX')).toHaveAttribute('href','/api/documents/sample/tables/0/export/xlsx'));
  const payload=JSON.parse(fetch.mock.calls[1][1].body);
  expect(payload.expected_revision).toBe(0);
  expect(payload.y_edges).toEqual([20,100]);
});

it('blocks invalid boundaries and shows save failures', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({ok:true,json:async()=>table}).mockResolvedValueOnce({ok:false,json:async()=>({detail:'Table changed in another tab.'})}));
  render(<TableWorkspace doc={doc} pageIndex={0} onBack={()=>{}}/>);
  await screen.findByText('Save table layout');
  fireEvent.change(screen.getByLabelText('Row boundaries'),{target:{value:'100,20'}});
  expect(screen.getByText('Save table layout')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Row boundaries'),{target:{value:'20,100'}});
  fireEvent.click(screen.getByText('Save table layout'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Table changed in another tab.');
  expect(parseEdges('0, 100, 200')).toEqual([0,100,200]);
});
