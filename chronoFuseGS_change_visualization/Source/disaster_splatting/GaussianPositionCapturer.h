// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SplattingActor.h"
#include "GaussianPositionCapturer.generated.h"

UCLASS()
class DISASTER_SPLATTING_API AGaussianPositionCapturer : public AActor
{
	GENERATED_BODY()
	
public:	
	// Sets default values for this actor's properties
	AGaussianPositionCapturer();

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:	
	// Called every frame
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(VisibleAnywhere)
	UTextureRenderTarget2D* StaticRT;

	UPROPERTY(EditAnywhere)
	bool UseRightHand; 

	UPROPERTY(EditAnywhere)
	FRotator ControllerOffsetRotation; 

	UFUNCTION(BlueprintCallable)
	FVector ReadPosition(float U, float V);

private:
	int32 RTWidth;
	int32 RTHeight;
	int32 RenderIndex = 0;
	float RenderResolution = 0.25; 
	bool RTInitialized = false;
	float PosMultiplier;
	FDelegateHandle ViewportResizedHandle;
	USceneCaptureComponent2D* CaptureComponent;
	ASplattingActor* SplattingActor;
	float FOVDeg = 10.0f;
	
	void TryInitializeRT();
	void InitRT();
	void OnViewportResized(FViewport* Viewport, uint32);
	void UpdateCapturer();
	FMatrix GetCaptureProjectionMatrix();
	// FMatrix GetCaptureClipToTranslatedWorld();
};
