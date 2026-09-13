FROM python:3.13-slim
WORKDIR /srv/lab
COPY shared ./shared
COPY weak-client-paywall ./weak-client-paywall
ENV PYTHONPATH=/srv/lab
ENV PORT=9102
EXPOSE 9102
CMD ["python3", "weak-client-paywall/server.py"]