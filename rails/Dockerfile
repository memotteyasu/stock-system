
FROM ruby:3.3.13-slim

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      build-essential \
      default-libmysqlclient-dev \
      pkg-config \
      git \
      curl \
      libyaml-dev \
      libvips \
      nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV RAILS_ENV=development \
    BUNDLE_PATH=/usr/local/bundle

COPY Gemfile Gemfile.lock ./

RUN bundle config set --local jobs 1 && \
    bundle install

COPY . .

EXPOSE 3000

CMD ["bin/rails", "server", "-b", "0.0.0.0"]

