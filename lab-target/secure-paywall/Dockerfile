FROM python:3.13-slim
WORKDIR /srv/lab
COPY shared ./shared
COPY secure-paywall ./secure-paywall
ENV PYTHONPATH=/srv/lab
ENV PORT=9101
EXPOSE 9101
CMD ["python3", "secure-paywall/server.py"]