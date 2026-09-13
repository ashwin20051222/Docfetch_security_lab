FROM python:3.13-slim
WORKDIR /srv/lab
COPY shared ./shared
COPY weak-direct-file ./weak-direct-file
ENV PYTHONPATH=/srv/lab
ENV PORT=9103
EXPOSE 9103
CMD ["python3", "weak-direct-file/server.py"]