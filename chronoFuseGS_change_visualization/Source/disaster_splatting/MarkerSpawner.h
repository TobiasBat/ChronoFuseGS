// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GaussianPositionCapturer.h"
#include "GameFramework/Actor.h"
#include "MarkerSpawner.generated.h"

UCLASS()
class DISASTER_SPLATTING_API AMarkerSpawner : public AActor
{
	GENERATED_BODY()
	
public:	
	// Sets default values for this actor's properties
	AMarkerSpawner();
	
	// UPROPERTY(EditAnywhere)
	// UTextureRenderTarget2D* PositionRT;

	UPROPERTY(EditAnywhere)
	TSubclassOf<AActor> BaseMarker;

	UPROPERTY(EditAnywhere)
	TSubclassOf<AActor> NextMarkMarker;
	
	UPROPERTY(EditAnywhere)
	TSubclassOf<AActor> TeleportationMarker;

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:	
	// Called every frame
	virtual void Tick(float DeltaTime) override;

	UFUNCTION(BlueprintCallable)
	void SpawnMarker(float U, float V);

	UFUNCTION(BlueprintCallable)
	void MoveTeleportationMarker();

	/**
	 * Legacy
	 */
	UFUNCTION(BlueprintCallable)
	void MoveNextMarker();

	/**s
	 * Legacy
	 */
	UFUNCTION(BlueprintCallable)
	void ShowTeleportationMarker(bool Show);

	UFUNCTION(BlueprintCallable)
	void ShowNextMarkMarker(bool Show);
private:
	double PosMultiplier; 
	AGaussianPositionCapturer* PositionCapturer;
	AActor* TeleportMarkerActor;
	AActor* NextMarkMarkerActor; 
	void InitActiveMarker();
	void InitNextMarkMarker();
};
