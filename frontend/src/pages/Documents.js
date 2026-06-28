import React, { useState, useEffect } from 'react';
import { documentService } from '../services/api';
import { Upload, Trash2, File, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

const Documents = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const data = await documentService.list();
      setDocuments(data.documents || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadError('');

    try {
      await documentService.upload(file);
      await fetchDocuments();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Failed to upload document. Please ensure it is a supported file type.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document from the vector store and database?')) return;
    try {
      await documentService.delete(docId);
      await fetchDocuments();
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner-border animate-spin"></div>
        <p>Syncing Document Vault...</p>
      </div>
    );
  }

  return (
    <div className="page-wrapper animate-fadeIn">
      <div className="page-header">
        <h1 className="text-gradient">Document Ingestion</h1>
        <p className="subtitle">Manage manuals, log books, emails and failure reports inside the vector vault</p>
      </div>

      {uploadError && <div className="error-alert-banner mb-4">{uploadError}</div>}

      <div className="documents-layout">
        {/* Upload Card */}
        <div className="upload-card glass flex flex-col items-center justify-center p-8 border-2 border-dashed border-slate-700 rounded-xl hover:border-cyan transition-all">
          <Upload size={48} className="text-cyan mb-4 animate-bounce" />
          <h3>Ingest New Document</h3>
          <p className="text-slate-400 text-xs text-center mt-2 max-w-xs">
            Supports PDF, DOCX, CSV, XLSX, TXT, LOG, EML and image files (PNG/JPG). Max 50MB.
          </p>
          <label className="btn-primary mt-6 cursor-pointer">
            {uploading ? (
              <>
                <RefreshCw size={18} className="animate-spin" />
                <span>Ingesting Chunks...</span>
              </>
            ) : (
              <>
                <span>Choose File</span>
                <input 
                  type="file" 
                  className="hidden" 
                  onChange={handleFileUpload} 
                  disabled={uploading} 
                />
              </>
            )}
          </label>
        </div>

        {/* Documents Vault List */}
        <div className="vault-card glass p-6 rounded-xl flex-1">
          <div className="vault-header border-b border-slate-700/50 pb-3 mb-4 flex justify-between items-center">
            <h3>Document Vault</h3>
            <span className="text-xs bg-slate-800 px-3 py-1 rounded-full text-slate-300">
              {documents.length} Files Ingested
            </span>
          </div>

          {documents.length === 0 ? (
            <div className="empty-vault-state flex flex-col items-center justify-center p-12 text-slate-500">
              <File size={36} className="mb-2" />
              <p>The vector vault is empty. Upload documents to enable dense semantic search.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="vault-table w-full text-left">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase">
                    <th className="py-2">File Info</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Chunks</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="border-b border-slate-800/50 hover:bg-slate-800/10 text-sm">
                      <td className="py-3 flex items-center gap-2">
                        <File size={16} className="text-cyan" />
                        <div>
                          <p className="font-bold text-slate-200">{doc.original_filename}</p>
                          <span className="text-[10px] text-slate-500 uppercase">{doc.file_type}</span>
                        </div>
                      </td>
                      <td className="text-slate-300">{formatBytes(doc.file_size_bytes)}</td>
                      <td>
                        <span className={`status-badge-pill ${doc.status}`}>
                          {doc.status === 'completed' && <CheckCircle2 size={12} className="inline mr-1 text-emerald-400" />}
                          {doc.status === 'failed' && <XCircle size={12} className="inline mr-1 text-red-400" />}
                          {doc.status === 'processing' && <RefreshCw size={12} className="inline mr-1 animate-spin text-amber-400" />}
                          <span>{doc.status}</span>
                        </span>
                      </td>
                      <td className="text-slate-300">{doc.chunk_count || 0}</td>
                      <td className="text-right">
                        <button 
                          className="delete-doc-btn text-red-400 hover:text-red-300 p-1"
                          onClick={() => handleDelete(doc.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Documents;
