"""Test /api/v1/knowledge/* endpoints — upload, list, search, delete."""

import pytest


@pytest.mark.asyncio
async def test_upload_txt(api_client, auth_headers, mock_chroma):
    """Upload a TXT file → 201 with document id."""
    resp = await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("hello.txt", "Hello, World!", "text/plain")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "hello.txt"
    assert data["content_type"] == "text/plain"
    assert data["file_size"] == 13
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 1  # "Hello, World!" → 1 chunk


@pytest.mark.asyncio
async def test_upload_md(api_client, auth_headers, mock_chroma):
    """Upload a Markdown file → 201."""
    content = "# Title\n\nSome **markdown** content here."
    resp = await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("doc.md", content, "text/markdown")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ready"
    assert data["content_type"] == "text/markdown"


@pytest.mark.asyncio
async def test_upload_unsupported_type(api_client, auth_headers, mock_chroma):
    """Upload unsupported file type → 400."""
    resp = await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("script.exe", b"\x00\x00", "application/x-msdownload")},
    )
    assert resp.status_code == 400
    data = resp.json()
    # The app uses structured error responses (message/detail)
    assert "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_list_documents(api_client, auth_headers, mock_chroma):
    """List all documents for the tenant."""
    # Upload two documents first
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("a.txt", "Content A", "text/plain")},
    )
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("b.txt", "Content B", "text/plain")},
    )

    resp = await api_client.get(
        "/api/v1/knowledge/documents",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_documents_with_status_filter(
    api_client, auth_headers, mock_chroma
):
    """Filter documents by status."""
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("test.txt", "Content", "text/plain")},
    )

    resp = await api_client.get(
        "/api/v1/knowledge/documents?status=ready",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "ready"


@pytest.mark.asyncio
async def test_get_document_by_id(api_client, auth_headers, mock_chroma):
    """Get a single document by ID."""
    upload = await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("target.txt", "Specific content", "text/plain")},
    )
    doc_id = upload.json()["id"]

    resp = await api_client.get(
        f"/api/v1/knowledge/documents/{doc_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == doc_id
    assert data["filename"] == "target.txt"


@pytest.mark.asyncio
async def test_get_document_not_found(api_client, auth_headers):
    """Get non-existent document → 404."""
    resp = await api_client.get(
        "/api/v1/knowledge/documents/99999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_document(api_client, auth_headers, mock_chroma):
    """Soft-delete a document → 204, then it disappears from list."""
    upload = await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("delete_me.txt", "Content to delete", "text/plain")},
    )
    doc_id = upload.json()["id"]

    resp = await api_client.delete(
        f"/api/v1/knowledge/documents/{doc_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Should not appear in list
    list_resp = await api_client.get(
        "/api/v1/knowledge/documents",
        headers=auth_headers,
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent(api_client, auth_headers):
    """Delete non-existent → 404."""
    resp = await api_client.delete(
        "/api/v1/knowledge/documents/99999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_documents(api_client, auth_headers, mock_chroma):
    """Search documents by filename keyword."""
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("quarterly_report_2026.pdf", "Fake PDF content for report", "application/pdf")},
    )
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("meeting_notes.txt", "Notes from the meeting", "text/plain")},
    )

    resp = await api_client.get(
        "/api/v1/knowledge/search?q=report",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["filename"] == "quarterly_report_2026.pdf"


@pytest.mark.asyncio
async def test_search_no_results(api_client, auth_headers, mock_chroma):
    """Search with no matches → 200 with empty list."""
    await api_client.post(
        "/api/v1/knowledge/upload",
        headers=auth_headers,
        files={"file": ("some_doc.txt", "Some content", "text/plain")},
    )
    resp = await api_client.get(
        "/api/v1/knowledge/search?q=nonexistent",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []
