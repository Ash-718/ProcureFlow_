FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q dependency:go-offline
COPY src ./src
RUN mvn -q package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/innovate-gov-backend.jar app.jar
RUN mkdir -p /uploads
EXPOSE 8001
ENTRYPOINT ["java", "-jar", "app.jar"]
