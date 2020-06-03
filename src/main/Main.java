/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package main;

import app.MainWindowController;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.stage.Stage;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.fxml.FXMLLoader;


public class Main extends Application {
	private MainWindowController contMain;
	private MainClass mainClass;
	
	@Override
	public void start(Stage primaryStage) {
		System.out.println("QuantumVITAS is launching.");
		try {
			mainClass = new MainClass();
			contMain = new MainWindowController(mainClass);
			FXMLLoader fxmlLoader = new FXMLLoader(this.getClass().getResource("/app/mainWindow.fxml"));
			fxmlLoader.setController(contMain);
            Parent root = fxmlLoader.load();
            
			Scene scene = new Scene(root,1280,800);
			scene.getStylesheets().add(getClass().getResource("/app/application.css").toExternalForm());
			
			primaryStage.setScene(scene);
			primaryStage.setOnCloseRequest(e->{
				System.out.println("QuantumVITAS is closing.");
				//close custom threads
			    if(mainClass!=null) {mainClass.jobManager.stop();}
			    if(contMain!=null) {contMain.killAllThreads();}
			    //standard closing
				Platform.exit();
				System.exit(0);
			});

			primaryStage.show();
		} catch(Exception e) {
			e.printStackTrace();
		}
	}
	public static void main(String[] args) {
		
		launch(args);
	}
}
