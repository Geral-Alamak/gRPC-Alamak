import os
import grpc
import psycopg2
import psycopg2.extras
from concurrent import futures

# Auto-compile the .proto file into Python classes before starting
if not os.path.exists("library_pb2.py"):
    from grpc_tools import protoc
    protoc.main((
        '',
        '-I.',
        '--python_out=.',
        '--grpc_python_out=.',
        'library.proto'
    ))

# Now import the freshly generated files
import library_pb2
import library_pb2_grpc

def _execute(query, params=None):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, params)
    conn.commit() 
    try:
        result = cursor.fetchall()
    except psycopg2.ProgrammingError:
        result = []
    cursor.close()
    conn.close()
    return result

class LibraryAPIServicer(library_pb2_grpc.LibraryAPIServicer):
    
    # --- Queries (Read) ---
    def GetAuthors(self, request, context):
        rows = _execute("SELECT * FROM authors")
        authors = [library_pb2.Author(author_id=r['author_id'], name=r['name']) for r in rows]
        return library_pb2.AuthorsResponse(authors=authors)

    def GetAuthor(self, request, context):
        rows = _execute("SELECT * FROM authors WHERE author_id = %s", (request.id,))
        if not rows:
            context.abort(grpc.StatusCode.NOT_FOUND, "Author not found")
        return library_pb2.Author(author_id=rows[0]['author_id'], name=rows[0]['name'])

    def GetBooks(self, request, context):
        rows = _execute("SELECT * FROM books")
        books = [library_pb2.Book(book_id=r['book_id'], title=r['title'], author_id=r['author_id']) for r in rows]
        return library_pb2.BooksResponse(books=books)

    def GetBook(self, request, context):
        rows = _execute("SELECT * FROM books WHERE book_id = %s", (request.id,))
        if not rows:
            context.abort(grpc.StatusCode.NOT_FOUND, "Book not found")
        return library_pb2.Book(book_id=rows[0]['book_id'], title=rows[0]['title'], author_id=rows[0]['author_id'])

    def GetReviews(self, request, context):
        rows = _execute("SELECT * FROM reviews")
        # Note: mapping SQL 'comment' to Proto 'review_text'
        reviews = [library_pb2.Review(review_id=r['review_id'], book_id=r['book_id'], rating=r['rating'], review_text=r['comment']) for r in rows]
        return library_pb2.ReviewsResponse(reviews=reviews)

    def GetReview(self, request, context):
        rows = _execute("SELECT * FROM reviews WHERE review_id = %s", (request.id,))
        if not rows:
            context.abort(grpc.StatusCode.NOT_FOUND, "Review not found")
        r = rows[0]
        return library_pb2.Review(review_id=r['review_id'], book_id=r['book_id'], rating=r['rating'], review_text=r['comment'])

    # --- Mutations (Write) ---
    def AddBook(self, request, context):
        sql = "INSERT INTO books (title, author_id) VALUES (%s, %s) RETURNING *"
        rows = _execute(sql, (request.title, request.author_id))
        r = rows[0]
        return library_pb2.Book(book_id=r['book_id'], title=r['title'], author_id=r['author_id'])

    def UpdateBook(self, request, context):
        fields = []
        params = []
        
        if request.title:
            fields.append("title = %s")
            params.append(request.title)
        if request.author_id:
            fields.append("author_id = %s")
            params.append(request.author_id)
            
        if not fields:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "No fields provided to update")
            
        params.append(request.id)
        sql = f"UPDATE books SET {', '.join(fields)} WHERE book_id = %s RETURNING *"
        rows = _execute(sql, tuple(params))
        
        if not rows:
            context.abort(grpc.StatusCode.NOT_FOUND, "Book not found")
            
        r = rows[0]
        return library_pb2.Book(book_id=r['book_id'], title=r['title'], author_id=r['author_id'])

    def DeleteBook(self, request, context):
        sql = "DELETE FROM books WHERE book_id = %s RETURNING book_id"
        rows = _execute(sql, (request.id,))
        return library_pb2.DeleteBookResponse(success=bool(rows))

def serve():
    # Cloud providers inject the required binding port via environment variables
    port = os.environ.get("PORT", "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    library_pb2_grpc.add_LibraryAPIServicer_to_server(LibraryAPIServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
