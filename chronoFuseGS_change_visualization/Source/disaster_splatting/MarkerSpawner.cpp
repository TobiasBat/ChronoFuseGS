// Fill out your copyright notice in the Description page of Project Settings.


#include "MarkerSpawner.h"
#include "GaussianPositionCapturer.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Kismet/GameplayStatics.h"

// Sets default values
AMarkerSpawner::AMarkerSpawner()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;
	
	PositionCapturer = nullptr;
	TeleportMarkerActor = nullptr;
	NextMarkMarkerActor = nullptr;
	
	PosMultiplier = 6000.0; 
}

// Called when the game starts or when spawned
void AMarkerSpawner::BeginPlay()
{
	Super::BeginPlay();
	PositionCapturer = Cast<AGaussianPositionCapturer>(UGameplayStatics::GetActorOfClass(GetWorld(), AGaussianPositionCapturer::StaticClass()));
}

// Called every frame
void AMarkerSpawner::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void AMarkerSpawner::SpawnMarker(float U, float V)
{
	UWorld* World = GetWorld();
	if (World)
	{
		FVector SpawnLocation = PositionCapturer->ReadPosition(U, V);
		FRotator SpawnRotation = FRotator::ZeroRotator;

		FActorSpawnParameters SpawnParams;
		SpawnParams.Owner = this;
		SpawnParams.Instigator = GetInstigator();
		
		AActor* SpawnedMarker = World->SpawnActor<AActor>(BaseMarker, SpawnLocation, SpawnRotation, SpawnParams);
		SpawnedMarker->SetActorHiddenInGame(false); 
		UE_LOG(LogTemp, Log, TEXT("Spanned new Marker at pos %f %f %f"), SpawnLocation.X, SpawnLocation.Y, SpawnLocation.Z); 
	}
}

void AMarkerSpawner::InitActiveMarker()
{
	UWorld* World = GetWorld();
	if (World)
	{
		FVector SpawnLocation = PositionCapturer->ReadPosition(0.5, 0.5);
		FRotator SpawnRotation = FRotator::ZeroRotator;

		FActorSpawnParameters SpawnParams;
		SpawnParams.Owner = this;
		SpawnParams.Instigator = GetInstigator();
		
		AActor* SpawnedMarker = World->SpawnActor<AActor>(TeleportationMarker, SpawnLocation, SpawnRotation, SpawnParams);
		SpawnedMarker->SetActorHiddenInGame(false);
		TeleportMarkerActor = SpawnedMarker; 
		UE_LOG(LogTemp, Log, TEXT("Spanned new Active Marker at pos %f %f %f"), SpawnLocation.X, SpawnLocation.Y, SpawnLocation.Z);

		TeleportMarkerActor->SetActorHiddenInGame(true);
	}
}

void AMarkerSpawner::MoveTeleportationMarker()
{
	if (TeleportMarkerActor != nullptr)
	{
		const FVector MoveLocations = PositionCapturer->ReadPosition(0.5, 0.5);
		TeleportMarkerActor->SetActorLocation(MoveLocations);
		TeleportMarkerActor->SetActorHiddenInGame(false);
	} else
	{
		InitActiveMarker(); 
	}
}

void AMarkerSpawner::MoveNextMarker()
{
	if (NextMarkMarkerActor != nullptr)
	{
		const FVector MoveLocations = PositionCapturer->ReadPosition(0.5, 0.5);
		NextMarkMarkerActor->SetActorLocation(MoveLocations);
		NextMarkMarkerActor->SetActorHiddenInGame(false);
	} else
	{
		InitNextMarkMarker();
	}
}

void AMarkerSpawner::ShowTeleportationMarker(bool Show)
{
	if (TeleportMarkerActor != nullptr)
		TeleportMarkerActor->SetActorHiddenInGame(!Show);
}

void AMarkerSpawner::ShowNextMarkMarker(bool show)
{
	if (NextMarkMarkerActor != nullptr)
		NextMarkMarkerActor->SetActorHiddenInGame(!show);
}

void AMarkerSpawner::InitNextMarkMarker()
{
	UWorld* World = GetWorld();
	if (World && NextMarkMarker)
	{
		FVector SpawnLocation = PositionCapturer->ReadPosition(0.5, 0.5);
		FRotator SpawnRotation = FRotator::ZeroRotator;

		FActorSpawnParameters SpawnParams;
		SpawnParams.Owner = this;
		SpawnParams.Instigator = GetInstigator();
		
		NextMarkMarkerActor = World->SpawnActor<AActor>(NextMarkMarker, SpawnLocation, SpawnRotation, SpawnParams);
		NextMarkMarkerActor->SetActorHiddenInGame(true);
		UE_LOG(LogTemp, Log, TEXT("Spanned new Active Marker at pos %f %f %f"), SpawnLocation.X, SpawnLocation.Y, SpawnLocation.Z);
	}
}
